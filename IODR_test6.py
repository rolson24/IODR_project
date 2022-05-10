from dash import Dash, dcc, html, Input, Output, State, callback_context
from plotly.subplots import make_subplots
from whitenoise import WhiteNoise

from functions import get_OD_dataframe as get_OD_dataframe
from functions import get_temp_data as get_temp_data
from functions import format_OD_data as format_OD_data
from functions import format_ln_data as format_ln_data
from functions import rename_tubes as rename_tubes
from functions import predict_curve as predict_curve

import numpy as np
import pandas as pd
import urllib.request
import requests
import json
import io
import plotly.graph_objects as go
import plotly.express as px

from rq import Queue
from worker import conn

import logging
from scipy.signal import find_peaks
from scipy.optimize import curve_fit
from scipy import stats

# set ThingSpeak variables
# 3 sets of data, since there are 3 IODR devices
tsBaseUrl = r'https://api.thingspeak.com/channels'

# IODR device numbers (as of 10-27-2020)
# 1: device in Zeppelin chamber
# 2: device in Montgolfier chamber
# 3:
# 4: temperature readings for all devices
devNames = ['IODR #1', 'IODR #2', 'IODR #3']
oldNames = ['tube 1', 'tube 2', 'tube 3', 'tube 4', 'tube 5', 'tube 6', 'tube 7', 'tube 8']
# needs to be put in dcc.Store
newNames = ['field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'field7', 'field8']

# dataFrames = []

numCallbacks = 0

chIDs = [405675, 441742, 469909, 890567]
readAPIkeys = ['18QZSI0X2YZG8491', 'CV0IFVPZ9ZEZCKA8', '27AE8M5DG8F0ZE44', 'M7RIW6KSSW15OGR1']


marks = dict()

for i in range(0,25):
    marks[-i] = {'label': f'-{i}'}

print(marks)


# can edit title and legend names
config = {
    'edits': {
        'legendText': True,
        'titleText': True
    }
}

def linear_curve(t, a, b):
    """
    fit data to linear model
    """
    return a*t + b


def estimate_times(lnDataframes, curve, target_vals):
    estimates = []
    for i in range(len(lnDataframes)):
        lnODdf = pd.read_json(lnDataframes[i], orient='table')
        popt, last_time_point, r = predict_curve(lnODdf, curve, [-2, 0])

        if len(popt) != 0:
            first_time_time = lnODdf.index[0]
            last_time_time = lnODdf.index[-1]
            print("add predictions")
            print(target_vals)
            # get where the ln curve intercepts the target line
            intercept_x = (np.log(float(target_vals[i])) - popt[1]) / popt[0]  # need to fix!!!!
            time_intercept_x = (intercept_x * pd.Timedelta(1, 'h')) + first_time_time  # need to fix!!!
            time_intercept_x_str = (time_intercept_x).strftime("%Y-%m-%d %H:%M:%S")

            estimates.append(time_intercept_x_str)
            # print(f"t predict")
            # # create an np array for time coordinates
            # t_predict = np.linspace((last_time_point + data_selection_slider[0]), intercept_x, 50)
            # selection_df = lnODdf.loc[
            #     (lnODdf.index > (last_time_time + data_selection_slider[0] * pd.Timedelta(1, 'h'))) & (
            #             lnODdf.index < last_time_time + data_selection_slider[1] * pd.Timedelta(1, 'h'))]
            # # selection_df.index = selection_df.index * pd.Timedelta(1, 'h') + ODdf_original.index[0]
            # # create array of y coordinates with linear curve calculated earlier
            # y_predict = linear_curve(t_predict, popt[0], popt[1])
            #
            # # print(type(ODdf_original.index[0]))
            # # ODdf_original['time'] = pd.to_datetime(ODdf_original['created_at']).dt.tz_convert('US/Eastern')
            # # change the time predict back to datatime objects
            # t_predict = (t_predict * pd.Timedelta(1, 'h')) + ODdf_original.index[0]
        else:
            estimates.append("none")
    return estimates

app = Dash(__name__)

server = app.server

# for heroku server
server.wsgi_app = WhiteNoise(server.wsgi_app, root='static/c')

app.layout = html.Div([
    html.Div(
        html.H1("IODR Data Browser", style={'textAlign': 'left', 'height': 150, 'width': '60%', 'float': 'left'})
    ),
    # get data button
    html.Div(
        children=[
            html.Button(
                'IODR #1',
                id='IODR1-button',
                className='IODR-button',
                style={'width': 100, 'height': 30}
            ),
            html.Button(
                'IODR #2',
                id='IODR2-button',
                className='IODR-button',
                style={'width': 100, 'height': 30}
            ),
            html.Button(
                'IODR #3',
                id='IODR3-button',
                className='IODR-button',
                style={'width': 100, 'height': 30}
            )
        ],
        id='button-div',
        style={'float': 'right', 'height': 150, 'width': '40%'}
    ),
    html.Div(),
    html.Br(),

    # graph html component
    html.Div(
        dcc.Loading(
            dcc.Graph(
                id='graph1')
        ),
        style={'marginTop': 150}
    ),
    # table to input tube names
    html.Div(children=[
        html.Table(children=[
            html.Thead(children=[
                html.Tr(children=[
                    html.Th(
                        children="Include Tube", scope='col'
                    ),
                    html.Th(
                        children="Name",
                        scope='col',
                        style={
                            'textAlign': 'center'
                        }
                    ),
                    html.Th(
                        children="Target OD",
                        scope='col',
                        style={
                            'textAlign': 'center'
                        }
                    ),
                    html.Th(
                        children="Est. Date/Time",
                        scope='col',
                        style={
                            'textAlign': 'center'
                        }
                    )
                ])
            ]),
            html.Tbody(children=[
                html.Td(
                    children=[
                        dcc.Checklist(
                            oldNames,
                            inline=True,
                            labelStyle=dict(
                                textAlign='right',
                                padding=10
                            ),
                            id='include-checklist'
                        ),
                    ],
                    rowSpan=0
                ),
                html.Tr(children=[
                    html.Td(
                        dcc.Input(id='tube-1-name', value=oldNames[0]),
                        className='tube-input'
                    ),
                    html.Td(
                        dcc.Input(id='tube-1-target', value=.5),
                        className='tube-input'
                    ),
                    html.Td(
                        id='tube-1-est'
                    )
                ]),
                html.Tr(children=[
                    html.Td(
                        dcc.Input(id='tube-2-name', value=oldNames[1]),
                        className='tube-input'
                    ),
                    html.Td(
                        dcc.Input(id='tube-2-target', value=.5),
                        className='tube-input'
                    ),
                    html.Td(
                        id='tube-2-est'
                    )
                ]),
                html.Tr(children=[
                    html.Td(
                        dcc.Input(id='tube-3-name', value=oldNames[2]),
                        className='tube-input'
                    ),
                    html.Td(
                        dcc.Input(id='tube-3-target', value=.5),
                        className='tube-input'
                    ),
                    html.Td(
                        id='tube-3-est'
                    )
                ]),
                html.Tr(children=[
                    html.Td(
                        dcc.Input(id='tube-4-name', value=oldNames[3]),
                        className='tube-input'
                    ),
                    html.Td(
                        dcc.Input(id='tube-4-target', value=.5),
                        className='tube-input'
                    ),
                    html.Td(
                        id='tube-4-est'
                    )
                ]),
                html.Tr(children=[
                    html.Td(
                        dcc.Input(id='tube-5-name', value=oldNames[4]),
                        className='tube-input'
                    ),
                    html.Td(
                        dcc.Input(id='tube-5-target', value=.5),
                        className='tube-input'
                    ),
                    html.Td(
                        id='tube-5-est'
                    )
                ]),
                html.Tr(children=[
                    html.Td(
                        dcc.Input(id='tube-6-name', value=oldNames[5]),
                        className='tube-input'
                    ),
                    html.Td(
                        dcc.Input(id='tube-6-target', value=.5),
                        className='tube-input'
                    ),
                    html.Td(
                        id='tube-6-est'
                    )
                ]),
                html.Tr(children=[
                    html.Td(
                        dcc.Input(id='tube-7-name', value=oldNames[6]),
                        className='tube-input'
                    ),
                    html.Td(
                        dcc.Input(id='tube-7-target', value=.5),
                        className='tube-input'
                    ),
                    html.Td(
                        id='tube-7-est'
                    )
                ]),
                html.Tr(children=[
                    html.Td(
                        dcc.Input(id='tube-8-name', value=oldNames[7]),
                        className='tube-input'
                    ),
                    html.Td(
                        dcc.Input(id='tube-8-target', value=.5),
                        className='tube-input'
                    ),
                    html.Td(
                        id='tube-8-est'
                    )
                ])
            ])],
            id='tube-name-table'
        ),
        html.Button(
            'Rename Tubes',
            id='rename-button',
            style={'width': 100, 'height': 60}
        )],
        id='rename-div'
    ),
    html.Br(),

    # tube selector dropdown
    html.Div(children=[
        html.H3("Tube Selector", style={'textAlign': 'center'}),
        dcc.Dropdown(newNames, id = 'tube-dropdown')],
        style={'flex': 1, 'width': '30%', 'marginLeft': '35%', 'marginTop': 100}
    ),

    # graph 3 is linear OD graph
    html.Div(children=[
        html.Div(
            dcc.Loading(
                dcc.Graph(
                    id='linearODgraph'
                )
            ),
            style={'width': '80%', 'flex': 1, 'float': 'left'}
        ),
        # limit slider
        html.Div(
            dcc.Slider(
                min=0,
                max=1,
                step=0.1,
                value=0.5,
                vertical=True,
                verticalHeight=300,
                disabled=False,
                id='OD_target_slider'
            ),
            style={'float': 'right', 'flex': 1, 'width': '15%', 'marginTop': 50}
        )
    ]),
    # graph 2 is ln OD graph
    # html.Div(
    #     dcc.Loading(
    #         dcc.Graph(
    #             id='lnODgraph'
    #         )
    #     ),
    #     style={'flex': 1, 'float': 'left'}
    # ),

    # prediction range slider
    html.Br(),
    html.Div(children=[
        html.H3("Prediction Curve range selection. (Hours before current time)", style={'textAlign': 'center'}),
        dcc.RangeSlider(
            min=-24,
            max=0,
            step=0.25,
            marks=marks,
            value=[-5, 0],
            id='data-selection-slider')],
        style={'flex': 1, 'marginTop': 800}
    ),
    html.Div(children=[
        html.H3("OD offset value", style={'textAlign': 'center'}),
        dcc.Input(
            value=0.01,
            id='blank-val-input'
        )],
        style={'flex': 1, 'marginTop': 15}
    ),
    html.H2("Instructions for use:", style={'textAlign': 'center'}),
    html.Br(),
    html.Div(children=[
        '''
        To use this dashboard, first click the button labeled with the device you want 
        to view data from. Doing so will pull the most recent 8000 data points 
        (1000 per tube) and display them on the scatter plot. This process takes about 
        3 seconds to display the graph Note, this data does not update in real-time. 
        In order to see the latest data, click the device button again.''',
        html.H4("Predict Curves"),
        '''Below the tube renaming table, there are two graphs that display the OD data from one select tube. The top 
        graph shows the original OD data, while the bottom graph shows the natural log of the data. To get a prediction, 
        first select the tube you want to work with via the dropdown menu. Then use the slider on the side of the graph 
        to set the target OD value you want the predict. Finally use the prediction curve slider to 
        select which data is used to make the prediction. Your selected range of data will be highlighted in orange. 
        The predicted growth curve will be displayed in green and the estimated date and time of when the strain reaches 
        the desired OD target with be shown in a purple box on the graph. To make small adjustments to the prediction, 
        you can adjust the offset of the clear OD value''',
        html.H4("Rename Traces"),
        '''To rename the traces on the graph, simply input the names of the bateria 
        strains that correspond to each tube.''',
        html.H4("Zoom"),
        '''To zoom in on a set of points, simply click and drag on the graph and a 
        selection box will appear showing the frame that will be zoomed to. To zoom back 
        out, double click on the graph and the graph will return to the original view.''',
        html.H4("Pan"),
        '''To pan the graph horizontally and vertically, click and drag on the labels of 
        the axes.''',
        html.H4("Show/Hide traces"),
        '''To turn individual traces off and on, click the name of the trace you want to 
        toggle in the legend of the graph. To turn all the traces off, double 
        click on the trace you want on. To turn all of the traces on, double click on any 
        of the trace names in the legend.''',
        html.H4("Save a picture"),
        '''To save a picture of the graph, hover your mouse over the graph and click the 
        camera icon in the upper right-hand corner.''',
        html.H4("Operational notes"),
        '''The app times out after 30 minutes of inactivity. You are still able to view 
        the current graph, but you must refresh the page to get the data from another 
        device.''',
        html.H5(children=['''Dashboard created by Raif Olson advised by Daniel Olson. 
        Full code at:  ''',
                          html.A(
                              "Github",
                              href="https://github.com/rolson24/IODR_project",
                              target="_blank",
                              rel="noopener noreferrer"
                          )]
                ),
    ],
        style={'marginLeft': 30, 'marginRight': 30, 'marginBottom': 30}),
    # storage components to share dataframes between callbacks
    dcc.Store(id='ODdf_original_store'),
    dcc.Store(id='IODR_store'),
    dcc.Store(data=newNames, id='newNames_store'),
    dcc.Store(id='lnDataframes_store'),
    dcc.Store(id='zoom_vals_store')

])


# callback for choosing which IODR to load
@app.callback(
    Output('IODR_store', 'data'),
    Input('IODR1-button', 'n_clicks'),
    Input('IODR2-button', 'n_clicks'),
    Input('IODR3-button', 'n_clicks'))
def update_which_IODR(IODR1_button, IODR2_button, IODR3_button):
    # checks which button was pressed
    changed_id = [p['prop_id'] for p in callback_context.triggered][0]
    if 'IODR1-button' in changed_id:
        device = 0
    elif 'IODR2-button' in changed_id:
        device = 1
    elif 'IODR3-button' in changed_id:
        device = 2
    else:
        device = 0
    return device


# callback for updating the main graph and tube dropdown when a new IODR is loaded
# or the rename tubes button is pressed
@app.callback(
    Output('graph1', 'figure'),
    Output('tube-dropdown', 'options'),
    Output('tube-dropdown', 'value'),
    Output('ODdf_original_store', 'data'),
    Output('newNames_store', 'data'),
    Output('lnDataframes_store', 'data'),
    Input('IODR_store', 'data'),
    Input('rename-button', 'n_clicks'),
    State('tube-dropdown', 'value'),
    State('tube-1-name', 'value'),
    State('tube-2-name', 'value'),
    State('tube-3-name', 'value'),
    State('tube-4-name', 'value'),
    State('tube-5-name', 'value'),
    State('tube-6-name', 'value'),
    State('tube-7-name', 'value'),
    State('tube-8-name', 'value'),
    State('newNames_store', 'data'))
def update_graph(device, rename_button, ln_tube, name_1, name_2, name_3, name_4, name_5, name_6, name_7, name_8, newNames):
    # get the index of the current tube selected in the dropdown to fix a bug
    tube_index = newNames.index(ln_tube) if ln_tube != None else 0
    # put the new names into the list
    newNames[0] = "1_" + name_1 if (name_1 != None and name_1 != "") else newNames[0]
    newNames[1] = "2_" + name_2 if (name_2 != None and name_2 != "") else newNames[1]
    newNames[2] = "3_" + name_3 if (name_3 != None and name_3 != "") else newNames[2]
    newNames[3] = "4_" + name_4 if (name_4 != None and name_4 != "") else newNames[3]
    newNames[4] = "5_" + name_5 if (name_5 != None and name_5 != "") else newNames[4]
    newNames[5] = "6_" + name_6 if (name_6 != None and name_6 != "") else newNames[5]
    newNames[6] = "7_" + name_7 if (name_7 != None and name_7 != "") else newNames[6]
    newNames[7] = "8_" + name_8 if (name_8 != None and name_8 != "") else newNames[7]
    # print(newNames)
    # make the subplots object
    figure1 = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("OD data", "Temperature"),
        row_heights=[0.8, 0.2],
        vertical_spacing=0.1)

    # checks which button was pressed
    changed_id = [p['prop_id'] for p in callback_context.triggered][0]
    if device == 0:
        figure1.update_layout(title="IODR #1")
    elif device == 1:
        figure1.update_layout(title="IODR #2")
    elif device == 2:
        figure1.update_layout(title="IODR #3")

    # retrieve the data from Thingspeak
    ODdf_original = get_OD_dataframe(device, chIDs, readAPIkeys)

    lnDataframes = []
    for i in range(len(newNames)):
        lndf = format_ln_data(ODdf_original, i).to_json(date_format='iso', orient='table')
        lnDataframes.append(lndf)

    # print("ODdf_original", type(ODdf_original.index[0]), ODdf_original)
    # ODdf = format_OD_data(ODdf_original)
    # print("ODdf", type(ODdf.index[0]), ODdf)
    TEMPdf = get_temp_data(device, chIDs, readAPIkeys)

    # rename the tubes on button press
    if 'rename-button' in changed_id:  # or numCallbacks == 0:
        rename_tubes(ODdf_original, newNames)

    # add the traces of each tube
    for col in ODdf_original.columns:
        figure1.add_trace(
            go.Scatter(
                x=ODdf_original.index,
                y=ODdf_original[col],
                mode='markers',
                marker_size=5,
                name=col,
                meta=col,
                # legendgroup="OD traces",
                # legendgrouptitle_text="OD traces",
                hovertemplate='Time: %{x}' +
                              '<br>OD: %{y}<br>' +
                              'Trace: %{meta}<br>' +
                              '<extra></extra>'),
            row=1,
            col=1)
    # add the traces of the temperature
    for col in TEMPdf.columns:
        figure1.add_trace(
            go.Scatter(
                x=TEMPdf.index,
                y=TEMPdf[col],
                mode='markers',
                marker_size=5,
                name=col,
                meta=col,
                legendgroup="Temp traces",
                legendgrouptitle_text="Temperature traces",
                hovertemplate='Time: %{x}' +
                              '<br>Temp: %{y}<br>' +
                              'Trace: %{meta}<br>' +
                              '<extra></extra>'),
            row=2,
            col=1)

    # align the x-axis
    figure1.update_xaxes(matches='x')
    # de-align the y-axes
    figure1.update_yaxes(matches=None)
    # set the range for the temperature y-axis
    figure1.update_yaxes(range=[30, 60], row=2, col=1)
    figure1.update_layout(
        height=800,
        font=dict(
            family='Open Sans',
            size=14
        ),
        legend_itemdoubleclick='toggleothers',
        legend_groupclick='toggleitem',
        legend_itemsizing='constant',
        # legend_tracegroupgap=320,
        hoverlabel_align='right')
    # return the ODdf_original dataframe as a json to the store component
    return figure1, newNames, newNames[tube_index], ODdf_original.to_json(date_format='iso', orient='table'), newNames, lnDataframes


# callback for the prediction graphs
@app.callback(
    Output('linearODgraph', 'figure'),
    Input('tube-dropdown', 'value'),
    Input('ODdf_original_store', 'data'),
    Input('OD_target_slider', 'value'),
    Input('data-selection-slider', 'value'),
    Input('blank-val-input', 'value'),
    Input('newNames_store', 'data'),
    State('tube-1-target', 'value'),
    State('tube-2-target', 'value'),
    State('tube-3-target', 'value'),
    State('tube-4-target', 'value'),
    State('tube-5-target', 'value'),
    State('tube-6-target', 'value'),
    State('tube-7-target', 'value'),
    State('tube-8-target', 'value'),
    State('lnDataframes_store', 'data'),
    State('zoom_vals_store', 'data')
)
def update_predict_graphs(fit_tube, ODdf_original_json, OD_target_slider, data_selection_slider, blank_value_input, newNames, tube_1_target, tube_2_target,  tube_3_target, tube_4_target, tube_5_target, tube_6_target, tube_7_target, tube_8_target, lnDataframes, zoom_vals):
    # read the dataframe in from the storage component
    ODdf_original = pd.read_json(ODdf_original_json, orient='table')
    #ODdf_original.index = ODdf_original.index - pd.Timedelta(4, 'h')

    targets = []
    targets.append(tube_1_target)
    targets.append(tube_2_target)
    targets.append(tube_3_target)
    targets.append(tube_4_target)
    targets.append(tube_5_target)
    targets.append(tube_6_target)
    targets.append(tube_7_target)
    targets.append(tube_8_target)

    # lnDataframes = []
    # for i in range(len(newNames)):
    #     lndf = format_ln_data(ODdf_original, newNames[i])
    #     if lnDataframes[i] is not None:
    #         lnDataframes.append(lndf)
    #     else:
    #         lnDataframes[i] = lndf

    print("estimate times values", estimate_times(lnDataframes, linear_curve, targets))

    try:
        blank_value_input = float(blank_value_input)
    except:
        blank_value_input = 0
    if fit_tube != None:
        # print("index", newNames.index(fit_tube))
        # format the data into a dataframe of just the selected tube's OD and lnOD data
        lnODdf = format_ln_data(ODdf_original, newNames.index(fit_tube), blank_value=float(blank_value_input))
    else:
        # print('tube 0')
        lnODdf = format_ln_data(ODdf_original, 0, blank_value=float(blank_value_input))
    # print("lnODdf", lnODdf)

    # use predict_curve function to predict the curve and get the last time point as a float
    popt, last_time_point, r = predict_curve(lnODdf, linear_curve, data_selection_slider)
    print("R value:  ", r)
    # lnFigure = px.scatter(lnODdf, x = 'time', y = 'lnOD')
    # linearFigure = px.scatter(lnODdf, x = 'time', y = 'OD')

    # print(type(lnODdf.index[0]))

    # create scatter plot for ln data

    predict_figure = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Linear OD Graph", "Natural Log OD Graph"),
        row_heights=[0.5, 0.5],
        vertical_spacing=0.2)

    predict_figure.add_trace(
        go.Scatter(
            x=lnODdf.index,
            y=lnODdf.lnOD,
            mode='markers',
            name='lnOD',
            meta='lnOD',
            marker=dict(
                color='blue'
            ),
            legendgroup="ln traces",
            legendgrouptitle_text="ln traces",
            hovertemplate='Time: %{x}' +
                          '<br>lnOD: %{y}<br>' +
                          'Trace: %{meta}<br>' +
                          '<extra></extra>',
            legendrank=3
        ),
        row=2,
        col=1
    )
    #     )
    # create scatter plot for linear data
    predict_figure.add_trace(
        go.Scatter(
            x=lnODdf.index,
            y=lnODdf.OD,
            mode='markers',
            name='OD',
            meta='OD',
            marker=dict(
                color='blue'
            ),
            legendgroup="linear traces",
            legendgrouptitle_text="linear traces",
            hovertemplate='Time: %{x}' +
                          '<br>OD: %{y}<br>' +
                          'Trace: %{meta}<br>' +
                          '<extra></extra>',
            legendrank=1
        ),
        row=1,
        col=1
    )
    # name the axes
    predict_figure.update_xaxes(
        title_text="Time",
        row=1,
        col=1
    )
    predict_figure.update_xaxes(
        title_text="Time",
        row=2,
        col=1
    )
    predict_figure.update_yaxes(
        title_text="OD",
        row=1,
        col=1
    )
    predict_figure.update_yaxes(
        title_text="ln OD",
        row=2,
        col=1
    )
    predict_figure.update_layout(height=800)

    if len(popt) != 0:
        last_time_time = lnODdf.index[-1]

        print("add predictions")
        # get where the ln curve intercepts the target line
        intercept_x = (np.log(OD_target_slider) - popt[1]) / popt[0]  # need to fix!!!!
        print(f"t predict")
        # create an np array for time coordinates
        t_predict = np.linspace((last_time_point + data_selection_slider[0]), intercept_x, 50)
        selection_df = lnODdf.loc[
            (lnODdf.index > (last_time_time + data_selection_slider[0] * pd.Timedelta(1, 'h'))) & (
                        lnODdf.index < last_time_time + data_selection_slider[1] * pd.Timedelta(1, 'h'))]
        # selection_df.index = selection_df.index * pd.Timedelta(1, 'h') + ODdf_original.index[0]
        # create array of y coordinates with linear curve calculated earlier
        y_predict = linear_curve(t_predict, popt[0], popt[1])

        # print(type(ODdf_original.index[0]))
        # ODdf_original['time'] = pd.to_datetime(ODdf_original['created_at']).dt.tz_convert('US/Eastern')
        # change the time predict back to datatime objects
        t_predict = (t_predict * pd.Timedelta(1, 'h')) + ODdf_original.index[0]

        # t_selection = (t_selection * pd.Timedelta(1, 'h')) + ODdf_original.index[0]
        # print("t selection: ", t_selection)
        # print(ODdf_original.index[0])
        # print(type(t_predict[0]), t_predict[0])
        # print(type(ODdf_original.index[0]), ODdf_original.index[0])
        # t_predict[0].to_numpy()
        # add the fit line trace
        predict_figure.add_trace(
            go.Scatter(
                x=t_predict,
                y=y_predict,
                mode='lines',
                name='lnOD prediction',
                meta='lnOD prediction',
                marker=dict(
                    color='green' if r**2 > 0.9 else 'red'
                ),
                legendgroup="ln traces",
                hovertemplate='Time: %{x}' +
                              '<br>lnOD: %{y}<br>' +
                              'Trace: %{meta}<br>' +
                              '<extra></extra>',
                legendrank=4
            ),
            row=2,
            col=1
        )
        predict_figure.add_trace(
            go.Scatter(
                x=selection_df.index,
                y=selection_df.lnOD,
                mode='markers',
                name="Selection",
                meta="Selection",
                marker=dict(
                    color='orange'
                ),
                hovertemplate='Time: %{x}' +
                              '<br>lnOD: %{y}<br>' +
                              'Trace: %{meta}<br>' +
                              '<extra></extra>',
                legendgroup="ln traces"
            ),
            row=2,
            col=1
        )
        # transform linear y coordinates into ln values
        y_predict_lin = np.exp(y_predict)
        # print(y_predict_lin)
        # add the ln fit curve trace
        predict_figure.add_trace(
            go.Scatter(
                x=t_predict,
                y=y_predict_lin,
                mode='lines',
                marker=dict(
                    color='green' if r**2 > 0.9 else 'red'
                ),
                name='OD prediction',
                meta='OD prediction',
                legendgroup="linear traces",
                hovertemplate='Time: %{x}' +
                              '<br>OD: %{y}<br>' +
                              'Trace: %{meta}<br>' +
                              '<extra></extra>',
                legendrank=2
            ),
            row=1,
            col=1
        )

        predict_figure.add_trace(
            go.Scatter(
                x=selection_df.index,
                y=selection_df.OD,
                mode="markers",
                name="Selection",
                meta="Selection",
                marker=dict(
                    color="orange"
                ),
                hovertemplate='Time: %{x}' +
                              '<br>OD: %{y}<br>' +
                              'Trace: %{meta}<br>' +
                              '<extra></extra>',
                legendgroup="linear traces"
            )
        )
        # get the last recorded time point as a datetime object
        first_time_time = lnODdf.index[0]

        # calculate the x coordinate when the ln curve intercepts the target line
        time_intercept_x = (intercept_x * pd.Timedelta(1, 'h')) + first_time_time  # need to fix!!!

        # print(time_intercept_x)
        predict_figure.add_vline(x=time_intercept_x, line_width=2, line_dash='dash', row=1, col=1)

        time_intercept_x_str = (time_intercept_x).strftime("%Y-%m-%d %H:%M:%S")
        first_time_str = (first_time_time - pd.Timedelta(4, 'h')).strftime("%Y-%m-%d %H:%M:%S")
        # range the axis
        # predict_figure.update_xaxes(range=[first_time_str, time_intercept_x_str], row=1, col=1)

        predict_figure.add_annotation(
            x=time_intercept_x_str,
            y=OD_target_slider,
            text=f"Time when growth hits target: {time_intercept_x_str}",
            font=dict(
                color="#ffffff"
            ),
            showarrow=False,
            xshift=-200,
            yshift=-20,
            align='center',
            bordercolor="orange",
            borderwidth=2,
            bgcolor="blue",
            opacity=.5,
        )
    predict_figure.update_layout(legend_tracegroupgap=320)
    predict_figure.add_hline(y=OD_target_slider, line_width=2, line_dash='dash', row=1, col=1)
    if len(zoom_vals) != 0:
        if zoom_vals[0] is True:
            predict_figure.update_xaxes(matches='x', autorange=True)
        else:
            predict_figure.update_xaxes(matches='x', range=zoom_vals)
    else:
        predict_figure.update_xaxes(matches='x')

    return predict_figure

@app.callback(
    Output('tube-1-est', 'children'),
    Output('tube-2-est', 'children'),
    Output('tube-3-est', 'children'),
    Output('tube-4-est', 'children'),
    Output('tube-5-est', 'children'),
    Output('tube-6-est', 'children'),
    Output('tube-7-est', 'children'),
    Output('tube-8-est', 'children'),
    Input('rename-button', 'value'),
    Input('ODdf_original_store', 'data'),
    State('tube-1-target', 'value'),
    State('tube-2-target', 'value'),
    State('tube-3-target', 'value'),
    State('tube-4-target', 'value'),
    State('tube-5-target', 'value'),
    State('tube-6-target', 'value'),
    State('tube-7-target', 'value'),
    State('tube-8-target', 'value'),
    State('lnDataframes_store', 'data'))
def update_estimates(rename_button, ODdf_original_json, tube_1_target, tube_2_target, tube_3_target, tube_4_target, tube_5_target, tube_6_target, tube_7_target, tube_8_target, lnDataframes):
    ODdf_original = pd.read_json(ODdf_original_json, orient='table')
    #ODdf_original.index = ODdf_original.index - pd.Timedelta(4, 'h')

    targets = []
    targets.append(tube_1_target)
    targets.append(tube_2_target)
    targets.append(tube_3_target)
    targets.append(tube_4_target)
    targets.append(tube_5_target)
    targets.append(tube_6_target)
    targets.append(tube_7_target)
    targets.append(tube_8_target)

    # lnDataframes = []
    # for i in range(len(newNames)):
    #     lndf = format_ln_data(ODdf_original, newNames[i])
    #     if lnDataframes[i] is not None:
    #         lnDataframes.append(lndf)
    #     else:
    #         lnDataframes[i] = lndf

    estimates = estimate_times(lnDataframes, linear_curve, targets)
    print("estimate times values", estimates)
    return estimates[0], estimates[1], estimates[2], estimates[3], estimates[4], estimates[5], estimates[6], estimates[7]

@app.callback(
    Output('zoom_vals_store', 'data'),
    Input('linearODgraph', 'relayoutData')
)
def zoom_event(relayout_data):
    data = []
    if relayout_data is not None:
        if 'xaxis.range[0]' in relayout_data:
            data.append(relayout_data['xaxis.range[0]'])
            data.append(relayout_data['xaxis.range[1]'])
            #data2 = relayout_data['xaxis.autorange']
            print(data)
            #print(data2)
        else:
            data = []
        if 'xaxis.autorange' in relayout_data:
            data.append(relayout_data['xaxis.autorange'])
            print(data)
    return data

if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)

