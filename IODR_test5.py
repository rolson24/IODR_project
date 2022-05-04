from dash import Dash, dcc, html, Input, Output, State, callback_context
from plotly.subplots import make_subplots
from whitenoise import WhiteNoise


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


def get_OD_dataframe(device):
    """Returns a data frame containing the OD data for the specified device.
    
    Arguments:
    device -- int device number (0-2)
    newNames -- list of strings for the names of each tube (expected length 8)
    
    relies on global variables chIDs and readAPIkeys
    """
    # select the channel ID and read API key depending on which device is being used
    # chID = chIDs[devNum-1]
    chID = chIDs[device]

    #readAPIkey = readAPIkeys[devNum-1]
    readAPIkey = readAPIkeys[device]

    # get data from Thingspeak
    myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?results=8000'.format(channel_id = chID)
    #myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?start=2021-09-20'.format(channel_id = chID)
    # print(myUrl)
    r = requests.get(myUrl)

    # put the thingspeak data in a dataframe
    df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
    
    print("the first df", df)
    
    df2 = df.drop('entry_id', axis = 'columns')
    print(df2)
    # convert time string to datetime, and switch from UTC to Eastern time
    print(df2)
    df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    print(df2)
    # remove the created_at column
    df3 = df2.drop('created_at', axis = 'columns')
    print(df3)
    # set index to time
    df4 = df3.set_index('time')

    first_time_time = df4.index[0]
    last_time_time = df4.index[-1]
    print("df4", df4)
    print("first time ", first_time_time)
    print("last time ", last_time_time)

    df5 = df4.loc[(df4.index > (last_time_time - pd.Timedelta(2, 'h'))) & (df4.index < last_time_time)]

    df6 = df4.loc[(df4.index > first_time_time) & (df4.index < last_time_time - pd.Timedelta(2, 'h'))]
    df7 = df6.iloc[::10]

    df8 = pd.concat([df7, df5])
    print("df8 ", df8)


    return df8

# Not being used
def format_OD_data(dataframe):
    """Returns a dataframe with the time strings switched to datetime objects
    
    Arguments:
    dataframe -- pandas dataframe with time column as strings formatted for time
    """
    df2 = dataframe.drop('entry_id', axis = 'columns')
    # convert time string to datetime, and switch from UTC to Eastern time
    df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    df3 = df2.drop('created_at', axis = 'columns')
    df4 = df3.set_index('time')
    # print(df4.head())
    return df4

def rename_tubes(dataframe, newNames):
    """Modifies the input dataframe inplace to rename the columns to the newNames list
    List must be the same length and order as the columns you want to rename
    
    Arguments:
    dataframe -- pandas dataframe (in this context, only columns are the traces)
    """
    # rename tubes on update
    i = 0
    # print("rename df", dataframe)
    for col in dataframe.columns:
        dataframe.rename(columns = {col : newNames[i]}, inplace=True)
        # print(newNames[i])
        i += 1
    
    return


def get_temp_data(device):
    """Returns a data frame containing the temperature data for the specified device
    
    Arguments:
    device -- int device number (0-2)
    
    relies on global variables chIDs and readAPIkeys
    """
    # select the channel ID and read API key for temperature data
    chID = chIDs[3]

    #readAPIkey = readAPIkeys[devNum-1]
    readAPIkey = readAPIkeys[3]

    # get data from Thingspeak
    myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?results=1500'.format(channel_id = chID)
    #myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?start=2021-09-20'.format(channel_id = chID)
    #print(myUrl)
    r = requests.get(myUrl)

    # put the thingspeak data in a dataframe
    df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))

    df2 = df.drop('entry_id', axis = 'columns')

    # convert time string to datetime, and switch from UTC to Eastern time
    df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    df2 = df2.drop('created_at', axis = 'columns')
    df2.set_index('time', inplace = True)

    # format data for temperature, inlcude only temperature that matches the device selected
    if(device == 0):
        df3 = df2.drop(['field3', 'field4', 'field5', 'field6'], axis = 'columns')
    elif (device == 1):
        df3 = df2.drop(['field1', 'field2', 'field5', 'field6'], axis = 'columns')
    else:
        df3 = df2.drop(['field1', 'field2', 'field3', 'field4'], axis = 'columns')
    
    # rename columns for graphing
    tempNames = {
           'field1' : 'Temp Int',
           'field2' : 'Temp Ext',
           'field3' : 'Temp Int',
           'field4' : 'Temp Ext',
           'field5' : 'Temp Int',
           'field6' : 'Temp Ext'
           }
    df3.rename(columns = tempNames, inplace=True)
    
    return df3

# can edit title and legend names
config = {
    'edits': {
        'legendText': True,
        'titleText': True
    }
}

def format_ln_data(dataframe, tube_num, blank_value=0.01):
    """Returns a tuple of a ln transformed dataframe and the last time value
    in the dataframe as a datetime object
    
    Arguments:
    dataframe -- pandas dataframe with time 
    """
    print("ln dataframe", dataframe.head())
    # get the name of the tube
    tube_name = dataframe.columns[tube_num]
    
    # create new dataframe with tube_names and time index
    df2 = dataframe.loc[:, [tube_name]].dropna()
    #df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    #df3 = df2.drop('created_at', axis = 'columns')
    #print(df2.head())
    #print(type(df2.index[0]))
    
    #print(df2.head())
    # df2['time'] = pd.to_timedelta(df2['created_at'])/pd.Timedelta(1, 'h')
    
    # rename tube column to OD
    df2.rename({tube_name:'OD'}, axis=1, inplace=True)
    df2['OD'] = df2['OD'] - blank_value
    print("OD after blank val sub", df2['OD'])
    # calculate the natural log
    df2['lnOD'] = np.log(df2['OD'])
    #print(df2['lnOD'])
    # get rid of empty values and 0 OD values so ln is not inf
    df2['lnOD'].replace('', np.nan, inplace=True)
    df2['OD'].replace(0, np.nan, inplace=True)
    df2.dropna(inplace=True)
    
    return df2
    
def linear_curve(t, a, b):
    """
    fit data to linear model
    """
    return a*t + b

def predict_curve(dataframe, curve, slider_vals):
    # copy the dataframe so not editing in place
    df = dataframe.copy()
    # change the index (time) to an hour number
    df.index = (df.index - df.index[0])/pd.Timedelta(1, 'h') # this is done here so data gets displayed in datetime
    # get the last time point in a float while here for displaying prediction
    last_time_point = df.index[-1]
    print(f"last time point val: {last_time_point}")
    print(f"slider val: {slider_vals}")
    # filter data so that only the data within the range is used
    df2 = df.loc[(df.index > (last_time_point + slider_vals[0])) & (df.index < last_time_point + slider_vals[1])]

    print("begin selection: ", (last_time_point + slider_vals[0]))
    print("end selection: ", last_time_point + slider_vals[1])

    print("cleaned lnOD ")
    print(df2)
    if not df2['lnOD'].empty:
        # do the curve fit
        popt, pcov = curve_fit(curve, df2.index, df2['lnOD'])
        print("popt", popt)
    else:
        print('no data')
        popt = np.array([]) # need to figure out what this should actually be
    
    return popt, last_time_point

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
                style={'width':100, 'height': 30}
            ),
            html.Button(
                'IODR #2',
                id='IODR2-button',
                className='IODR-button',
                style={'width':100, 'height': 30}
            ),
            html.Button(
                'IODR #3',
                id='IODR3-button',
                className='IODR-button',
                style={'width':100, 'height': 30}
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
                        children="Tube", scope='col'
                    ),
                    html.Th(
                        children="Name",
                        scope='col',
                        style={
                            'textAlign': 'center'
                        }
                    )
                ])
            ]),
            html.Tbody(children=[
                html.Tr(children=[
                    html.Th('1', scope='row', className='tube-num-input'),
                    html.Td(
                        dcc.Input(id='tube-1-name', value=newNames[0]),
                        className='tube-input'
                    )
                ]),
                html.Tr(children=[
                    html.Th('2', scope='row', className='tube-num-input'),
                    html.Td(
                        dcc.Input(id='tube-2-name', value=newNames[1]),
                        className='tube-input'
                    )
                ]),
                html.Tr(children=[
                    html.Th('3', scope='row', className='tube-num-input'),
                    html.Td(
                        dcc.Input(id='tube-3-name', value=newNames[2]),
                        className='tube-input'
                    )
                ]),
                html.Tr(children=[
                    html.Th('4', scope='row', className='tube-num-input'),
                    html.Td(
                        dcc.Input(id='tube-4-name', value=newNames[3]),
                        className='tube-input'
                    )
                ]),
                html.Tr(children=[
                    html.Th('5', scope='row', className='tube-num-input'),
                    html.Td(
                        dcc.Input(id='tube-5-name', value=newNames[4]),
                        className='tube-input'
                    )
                ]),
                html.Tr(children=[
                    html.Th('6', scope='row', className='tube-num-input'),
                    html.Td(
                        dcc.Input(id='tube-6-name', value=newNames[5]),
                        className='tube-input'
                    )
                ]),
                html.Tr(children=[
                    html.Th('7', scope='row', className='tube-num-input'),
                    html.Td(
                        dcc.Input(id='tube-7-name', value=newNames[6]),
                        className='tube-input'
                    )
                ]),
                html.Tr(children=[
                    html.Th('8', scope='row', className='tube-num-input'),
                    html.Td(
                        dcc.Input(id='tube-8-name', value=newNames[7]),
                        className='tube-input'
                    )
                ])
            ])],
            id='tube-name-table'
        ),
        html.Button(
            'Rename Tubes',
            id='rename-button',
            style={'width':100, 'height': 60}
        )],
        id='rename-div'
    ),
    html.Br(),

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
    # tube selector dropdown
    html.Div(children=[
        html.H3("Tube Selector", style={'textAlign': 'center'}),
        dcc.Dropdown(newNames, id = 'tube-dropdown')],
        style={'flex': 1, 'marginTop': 900, 'width': '30%', 'marginLeft': '35%'}
    ),
    # prediction range slider
    html.Br(),
    html.Div(children=[
        html.H3("Prediction Curve range selection. (Hours before current time)", style={'textAlign': 'center'}),
        dcc.RangeSlider(
            min=-24,
            max=0,
            step=0.5,
            value=[-5, 0],
            id = 'data-selection-slider')],
        style={'flex': 1, 'marginTop': 15}
    ),
    html.Div(children=[
        html.H3("OD offset value", style={'textAlign': 'center'}),
        dcc.Slider(
            min=0,
            max=.1,
            step=0.01,
            value=0.01,
            id='blank-val-slider')],
        style={'flex': 1, 'marginTop': 15}
    ),
    html.Br(),
    html.Br(),
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
        html.H4("Rename Tubes"),
        '''To rename the traces on the graph, simply input the names of the bacteria 
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
        dcc.Store(data=newNames, id='newNames_store')
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
    newNames[0] = name_1 if (name_1 != None and name_1 != "") else newNames[0]
    newNames[1] = name_2 if (name_2 != None and name_2 != "") else newNames[1]
    newNames[2] = name_3 if (name_3 != None and name_3 != "") else newNames[2]
    newNames[3] = name_4 if (name_4 != None and name_4 != "") else newNames[3]
    newNames[4] = name_5 if (name_5 != None and name_5 != "") else newNames[4]
    newNames[5] = name_6 if (name_6 != None and name_6 != "") else newNames[5]
    newNames[6] = name_7 if (name_7 != None and name_7 != "") else newNames[6]
    newNames[7] = name_8 if (name_8 != None and name_8 != "") else newNames[7]
    # print(newNames)
    # make the subplots object
    figure1 = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("OD data", "Temperature"),
        row_heights=[0.8, 0.2],
        vertical_spacing = 0.1)
    
    # checks which button was pressed
    changed_id = [p['prop_id'] for p in callback_context.triggered][0]
    if device == 0:
        figure1.update_layout(title="IODR #1")
    elif device == 1:
        figure1.update_layout(title="IODR #2")
    elif device == 2:
        figure1.update_layout(title="IODR #3")
    
    # retrieve the data from Thingspeak
    ODdf_original = get_OD_dataframe(device)
    #print("ODdf_original", type(ODdf_original.index[0]), ODdf_original)
    #ODdf = format_OD_data(ODdf_original)
    #print("ODdf", type(ODdf.index[0]), ODdf)
    TEMPdf = get_temp_data(device)
    
    # rename the tubes on button press
    if 'rename-button' in changed_id: #or numCallbacks == 0:
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
                'Trace: %{meta}<br>'+
                '<extra></extra>'),
            row = 1,
            col = 1)
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
                'Trace: %{meta}<br>'+
                '<extra></extra>'), 
            row = 2,
            col = 1)

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
    return figure1, newNames, newNames[tube_index], ODdf_original.to_json(date_format='iso', orient='split'), newNames

# callback for the prediction graphs
@app.callback(
    Output('linearODgraph', 'figure'),
    Input('tube-dropdown', 'value'),
    Input('ODdf_original_store', 'data'),
    Input('OD_target_slider', 'value'),
    Input('data-selection-slider', 'value'),
    Input('blank-val-slider', 'value'),
    Input('newNames_store', 'data')
)
def update_predict_graphs(fit_tube, ODdf_original_json, OD_target_slider, data_selection_slider, blank_value_slider, newNames):
    # read the dataframe in from the storage component
    ODdf_original = pd.read_json(ODdf_original_json, orient='split')
    ODdf_original.index = ODdf_original.index - pd.Timedelta(4, 'h')
    if fit_tube != None:
        #print("index", newNames.index(fit_tube))
        # format the data into a dataframe of just the selected tube's OD and lnOD data
        lnODdf = format_ln_data(ODdf_original, newNames.index(fit_tube), blank_value=blank_value_slider)
    else:
        #print('tube 0')
        lnODdf = format_ln_data(ODdf_original, 0, blank_value=blank_value_slider)
    #print("lnODdf", lnODdf)
    
    # use predict_curve function to predict the curve and get the last time point as a float
    popt, last_time_point = predict_curve(lnODdf, linear_curve, data_selection_slider)
    # lnFigure = px.scatter(lnODdf, x = 'time', y = 'lnOD')
    #linearFigure = px.scatter(lnODdf, x = 'time', y = 'OD')
    
    #print(type(lnODdf.index[0]))
    
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
    
    if popt.any():
        last_time_time = lnODdf.index[-1]

        print("add predictions")
        # get where the ln curve intercepts the target line
        intercept_x = (np.log(OD_target_slider) - popt[1])/popt[0] #need to fix!!!!
        print(f"t predict")
        # create an np array for time coordinates
        t_predict = np.linspace((last_time_point + data_selection_slider[0]), intercept_x, 50)
        selection_df = lnODdf.loc[(lnODdf.index > (last_time_time + data_selection_slider[0] * pd.Timedelta(1, 'h'))) & (lnODdf.index < last_time_time + data_selection_slider[1] * pd.Timedelta(1, 'h'))]
        # selection_df.index = selection_df.index * pd.Timedelta(1, 'h') + ODdf_original.index[0]
        # create array of y coordinates with linear curve calculated earlier
        y_predict = linear_curve(t_predict, popt[0], popt[1])

        #print(type(ODdf_original.index[0]))
        #ODdf_original['time'] = pd.to_datetime(ODdf_original['created_at']).dt.tz_convert('US/Eastern')
        # change the time predict back to datatime objects
        t_predict = (t_predict*pd.Timedelta(1, 'h')) + ODdf_original.index[0]

        # t_selection = (t_selection * pd.Timedelta(1, 'h')) + ODdf_original.index[0]
        # print("t selection: ", t_selection)
        #print(ODdf_original.index[0])
        #print(type(t_predict[0]), t_predict[0])
        #print(type(ODdf_original.index[0]), ODdf_original.index[0])
        #t_predict[0].to_numpy()
        # add the fit line trace
        predict_figure.add_trace(
            go.Scatter(
                x=t_predict,
                y=y_predict,
                mode='lines',
                name='lnOD prediction',
                meta='lnOD prediction',
                marker=dict(
                    color='green'
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
        #print(y_predict_lin)
        # add the ln fit curve trace
        predict_figure.add_trace(
            go.Scatter(
                x=t_predict,
                y=y_predict_lin,
                mode='lines',
                name='OD prediction',
                meta='OD prediction',
                marker=dict(
                    color='green'
                ),
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
        time_intercept_x = (intercept_x*pd.Timedelta(1, 'h')) + first_time_time #need to fix!!!
        
        #print(time_intercept_x)
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
    predict_figure.update_xaxes(matches='x')

    return predict_figure


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)

