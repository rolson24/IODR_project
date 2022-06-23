from dash import Dash, dcc, html, Input, Output, State, callback_context, dash_table
import dash_bootstrap_components as dbc
from dash_bootstrap_components._components.Container import Container
from plotly.subplots import make_subplots
from whitenoise import WhiteNoise

from get_data_funs import *
from predict_funs import *

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
originalNames = ['field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'field7', 'field8']

numCallbacks = 0

# Thingspeak information
chIDs = [405675, 441742, 469909, 890567]
readAPIkeys = ['18QZSI0X2YZG8491', 'CV0IFVPZ9ZEZCKA8', '27AE8M5DG8F0ZE44', 'M7RIW6KSSW15OGR1']

# used for creating tick marks on data selection range slider
range_slider_marks = dict()

for i in range(0, 25):
    range_slider_marks[-i] = {'label': f'-{i}'}

colors = ['#f2a367', '#ed7091', '#61d0ef', '#5bc89b', '#f6cb67', '#de5f46', '#f19ef9', '#6371f2']

# creates the instance of the dash app
app = Dash(__name__, external_stylesheets=['/style.css'])
# creates the server to use by heroku server
server = app.server

# for heroku server, will find source
server.wsgi_app = WhiteNoise(server.wsgi_app, root='static/c')

# the html layout of the app
app.layout = html.Div([
    # this is the sticky header division at the top of the page
    html.Div(children=[
        html.H1("IODR #2 Viewer", id='header-text',
                style={'textAlign': 'left', 'height': 70, 'width': '27%', 'float': 'left', 'marginLeft': '3%'}),
        html.Div(children=[
            html.Button(
                'IODR #1',
                id='IODR1-button',
                className='IODR-button',
                style={'width': 130, 'height': 50, 'font-size': 20}
            ),
            html.Button(
                'IODR #2',
                id='IODR2-button',
                className='IODR-button',
                style={'width': 130, 'height': 50, 'font-size': 20}
            ),
            html.Button(
                'IODR #3',
                id='IODR3-button',
                className='IODR-button',
                style={'width': 130, 'height': 50, 'font-size': 20}
            ),
            html.Button(
                'Download CSV',
                id='download-button',
                className='download-button',
                style={'width': 130, 'height': 50, 'font-size': 20}
            ),
            dcc.Download(id='download-dataframe-csv')
        ],
            id='button-div',
            style={'float': 'right', 'height': 100, 'width': '70%'}
        )],
        style={
            'margin': 0,
            'padding': 0,
            # 'overflow': 'hidden',
            # 'background-color': '#333',
            'position': 'fixed',  # make the header sticky
            'width': '100%',  # 100% of the page
            'zIndex': 999,  # on top of all other divs
            'backgroundColor': 'white',
            'top': 0,
            'border-style': 'solid',
            'borderColor': 'black',
            'borderWidth': '0px 0px 3px'  # bottom border only
        },
        id='fixed-div'
    ),
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
        html.Div(children=[
            # the dash table element
            dash_table.DataTable(
                id='test_datatable',
                # create the columns
                columns=[
                    {'name': 'Tube Name', 'id': 'name', 'type': 'text', 'editable': True},
                    {'name': 'Target OD', 'id': 'target', 'type': 'numeric', 'editable': True},
                    {'name': 'OD Offset', 'id': 'offset', 'type': 'numeric', 'editable': True},
                    {'name': 'Est. Time/Date', 'id': 'estimate', 'type': 'text', 'editable': False},
                    {'name': 'R value', 'id': 'r value', 'type': 'numeric', 'editable': False}
                ],
                # input some data on startup
                data=[
                    {'name': 'tube 1'},
                    {'target': .5}
                ],
                # this makes the data red or green depending on the r^2 values of the estimate lines
                style_data_conditional=[
                    {'if': {'column_id': 'estimate', 'filter_query': '{r value} < .9'}, 'color': 'red'},
                    {'if': {'column_id': 'r value', 'filter_query': '{r value} < .9'},
                     'color': 'red'},
                    {'if': {'column_id': 'estimate', 'filter_query': '{r value} eq none'},
                     'color': 'red'},
                    {'if': {'column_id': 'r value', 'filter_query': '{r value} eq none'},
                     'color': 'red'},
                    {'if': {'column_id': 'estimate', 'filter_query': '{r value} > .9'}, 'color': 'green'},
                    {'if': {'column_id': 'r value', 'filter_query': '{r value} > .9'}, 'color': 'green'}
                ],
                fill_width=False,
                style_table={'overflowX': 'auto'},  # helps size the table
                style_cell={'minWidth': '160px', 'width': '160px', 'maxWidth': '160px', 'textAlign': 'center'}
                # style={'width': '50%'}

            ),

        ],
            style={'width': 800, 'flex': 1, 'float': 'left', 'marginLeft': 100}
        ),

        html.Button(
            'Download table',
            id='download-table-button',
            style={'width': 100, 'height': 60, 'font-size': 20}
        ),
        html.Button(
            'Clear',
            id='clear-button',
            style={'width': 100, 'height': 60, 'font-size': 20}
        ),
        html.Button(
            'Update Tubes',
            id='update-button',
            style={'width': 100, 'height': 60, 'font-size': 20}
        ),
        dcc.Download('download-table-csv')],
        id='update-div'
    ),
    html.Br(),
    html.Hr(style={'size': 30}),

    # tube selector dropdown
    html.Div(children=[
        html.H3("Tube Selector", style={'textAlign': 'center'}),
        dcc.Dropdown(originalNames, id='tube-dropdown')],
        style={'flex': 1, 'width': '30%', 'marginLeft': '35%', 'marginTop': 30}
    ),

    # graph 3 is linear OD graph
    html.Div(children=[
        html.Div(
            dcc.Loading(
                dcc.Graph(
                    id='linearODgraph'
                )
            ),
            style={'width': '90%', 'flex': 1, 'float': 'left'}
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
            style={'float': 'left', 'flex': 1, 'width': 30, 'marginTop': 50}
        )
    ]),

    # prediction range slider
    html.Br(),
    html.Div(children=[
        html.Div(children=[
            html.H3("Prediction Curve range selection. (Hours before current time)", style={'textAlign': 'center'}),
            # range slider dash element
            dcc.RangeSlider(
                min=-24,
                max=0,
                step=0.25,
                marks=range_slider_marks,
                value=[-5, 0],
                id='data-selection-slider'
            )],
            style={'width': '80%', 'float': 'left'}
        ),
        html.Div(children=[
            html.H3("OD offset value", style={'textAlign': 'center'}),
            # dash input element
            dcc.Input(
                value=0.01,
                id='blank-val-input',
                style={'float': 'right', 'marginRight': 80}
            )],
            style={'flex': 1, 'marginTop': 15, 'float': 'right', 'width': '20%'}
        ),
    ],
        style={'flex': 1, 'marginTop': 800, 'width': '80%'}

    ),
    html.Br(),
    html.Div(children=[
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
    ],
        style={'marginTop': 150}
    ),
    # storage components to share dataframes between callbacks
    dcc.Store(id='ODdf_original_full_store'),  # 8000 point dataframe as a json
    dcc.Store(id='ODdf_original_store'),  # thinned OD dataframe before renaming and offset vals changed (json)
    dcc.Store(id='ODdf_update_store'),  # final OD dataframe used for making graphs (json)
    dcc.Store(id='temp_df_store'),  # temperature dataframe (json)
    dcc.Store(id='IODR_store', data=1),  # IODR number store
    dcc.Store(data=[oldNames.copy(), oldNames.copy(), oldNames.copy()], id='newNames_store'),  # names of the tubes
    dcc.Store(id='lnDataframes_store'),  # ln dataframes, could be put into one dataframe (json)
    dcc.Store(id='zoom_vals_store'),  # values of zoom to maintain zoom levels when changing inputs for analysis
    # stores the three table dataframes as jsons
    dcc.Store(
        id='table_store',
        data=[
            # give the dataframes preset values for loading into the table initially
            pd.DataFrame(
                data={
                    'name': oldNames,
                    'target': [.5] * 8,
                    'offset': [0] * 8,
                    'estimate': [0] * 8,
                    'r value': [0] * 8
                }
            ).to_json(date_format='iso', orient='table'),
            pd.DataFrame(
                data={
                    'name': oldNames,
                    'target': [.5] * 8,
                    'offset': [0] * 8,
                    'estimate': [0] * 8,
                    'r value': [0] * 8
                }
            ).to_json(date_format='iso', orient='table'),
            pd.DataFrame(
                data={
                    'name': oldNames,
                    'target': [.5] * 8,
                    'offset': [0] * 8,
                    'estimate': [0] * 8,
                    'r value': [0] * 8
                }
            ).to_json(date_format='iso', orient='table'),
        ]
    )

])


# callback for choosing which IODR to load
@app.callback(
    Output('IODR_store', 'data'),
    Output('ODdf_original_full_store', 'data'),
    Output('ODdf_original_store', 'data'),
    Output('temp_df_store', 'data'),
    Output('header-text', 'children'),
    Input('IODR1-button', 'n_clicks'),
    Input('IODR2-button', 'n_clicks'),
    Input('IODR3-button', 'n_clicks')
)
def update_which_IODR(IODR1_button, IODR2_button, IODR3_button):  # load data on switch
    # checks which button was pressed
    changed_id = [p['prop_id'] for p in callback_context.triggered][0]

    if 'IODR1-button' in changed_id:
        device_num = 0
    elif 'IODR2-button' in changed_id:
        device_num = 1
    elif 'IODR3-button' in changed_id:
        device_num = 2
    else:
        device_num = 1

    ODdf_original, ODdf_original_full = get_OD_dataframe(device_num, chIDs, readAPIkeys)
    TEMPdf, TEMPdf_full = get_temp_data(device_num, chIDs, readAPIkeys)

    header_text = f"IODR #{device_num + 1} Viewer"

    return device_num, ODdf_original_full.to_json(date_format='iso', orient='table'), ODdf_original.to_json(
        date_format='iso', orient='table'), TEMPdf.to_json(date_format='iso', orient='table'), header_text


@app.callback(
    Output('table_store', 'data'),
    Output('ODdf_update_store', 'data'),
    Input('update-button', 'n_clicks'),
    Input('clear-button', 'n_clicks'),
    Input('IODR_store', 'data'),
    State('table_store', 'data'),
    State('ODdf_original_store', 'data'),
    State('test_datatable', 'data'),
)
def update_table_df(update_button, clear_button, device_num, tables_list, ODdf_original_json, datatable_dict):
    # dataframe to store the info from the table
    table_df = pd.read_json(tables_list[device_num], orient='table')
    ODdf_original = pd.read_json(ODdf_original_json, orient='table')
    print("beginnninggg!!!")
    print(ODdf_original)

    # the original info from the table in a dataframe
    datatable_df = pd.DataFrame.from_records(datatable_dict)

    newNames = datatable_df['name']  # names from the table
    targets = datatable_df['target']  # targets from the table
    print(f"targets {targets}")

    # checks which button was pressed
    changed_id = [p['prop_id'] for p in callback_context.triggered][0]
    if 'update-button' in changed_id:
        for i in range(8):  # 8 for 8 tubes
            newName = newNames[i]
            target = targets[i]
            if newName is not None and newName != "":
                table_df['name'].iloc[
                    i] = f"{i + 1}_" + newName  # add the tube num infront of name and put into storage dataframe

            if target is not None:
                try:
                    target = float(target)  # check if target string is a number
                except:
                    target = table_df['target'].iloc[i]  # if not keep it the same
                table_df['target'].iloc[i] = target

        rename_tubes(ODdf_original, table_df['name'])  # rename the tubes

        try:
            print("Success!!!")
            table_df['offset'] = pd.DataFrame.from_records(datatable_dict)['offset']
        except:
            print("Failed!!!")
            table_df['offset'] = [0] * 8

        for j in range(8):
            ODdf_original.iloc[:, j] = ODdf_original.iloc[:, j] + table_df['offset'].iloc[j]
            print(ODdf_original.iloc[:, j])

        lnDataframes = []  # Get rid of store component and just do it all here
        for i in range(8):
            lndf = format_ln_data(ODdf_original, i).to_json(date_format='iso', orient='table')
            lnDataframes.append(lndf)

        estimates, r_vals = estimate_times(lnDataframes, targets)

        table_df['estimate'] = estimates
        table_df['r value'] = r_vals
    elif 'clear-button' in changed_id:
        table_df['target'] = [.5] * 8
        table_df['name'] = oldNames
        table_df['estimate'] = ["none"] * 8
        table_df['r value'] = [0] * 8
        table_df['offset'] = [0] * 8
    else:
        rename_tubes(ODdf_original, table_df['name'])
        targets = [.5] * 8

        lnDataframes = []  # Get rid of store component and just do it all here
        for i in range(8):
            lndf = format_ln_data(ODdf_original, i, offset_value=table_df['offset'].iloc[i]).to_json(date_format='iso',
                                                                                                     orient='table')
            lnDataframes.append(lndf)
        estimates, r_vals = estimate_times(lnDataframes, targets)

        table_df['estimate'] = estimates
        table_df['r value'] = r_vals

    tables_list[device_num] = table_df.to_json(date_format='iso', orient='table')

    return tables_list, ODdf_original.to_json(date_format='iso', orient='table')


@app.callback(
    Output('test_datatable', 'data'),  # need to test this
    Input('table_store', 'data'),
    State('IODR_store', 'data'),
    prevent_initial_call=True)
def update_table_display(tables_list, device_num):
    table_df = pd.read_json(tables_list[device_num], orient='table')

    estimates = table_df['estimate']
    r_vals = table_df['r value']
    times = []
    print("estimate times values", estimates)
    for i in range(len(estimates)):  # need to display this in a different callback
        times.append(html.Div(children=estimates[i],
                              style={'color': 'green'} if float(r_vals[i]) > 0.9 else {'color': 'red'}))

    current_names = table_df['name']  # need to fix this so that it shows up correctly in table
    new_names = [""] * 8
    for i in range(len(new_names)):
        new_names[i] = current_names[i].replace(f"{i + 1}_", "")
        table_df['name'].iloc[i] = current_names[i].replace(f"{i + 1}_", "")

    return table_df.to_dict('records')


@app.callback(
    Output('download-dataframe-csv', 'data'),
    Input('download-button', 'n_clicks'),
    State('ODdf_original_full_store', 'data'),
    State('IODR_store', 'data'),
    prevent_initial_call=True
)
def download_csv(download_button, ODdf_original_full_json, device):
    ODdf_original_full = pd.read_json(ODdf_original_full_json, orient='table')
    return dcc.send_data_frame(ODdf_original_full.to_csv, f"IODR{device + 1}.csv")


@app.callback(
    Output('download-table-csv', 'data'),
    Input('download-table-button', 'n_clicks'),
    State('table_store', 'data'),
    State('IODR_store', 'data'),
    prevent_initial_call=True
)
def download_table(download_table_button, tables_list, device_num):
    table_df = pd.read_json(tables_list[device_num], orient='table')
    return dcc.send_data_frame(table_df.to_csv, f"IODR_{device_num + 1}_estimates_table.csv")


@app.callback(
    Output('tube-dropdown', 'options'),
    Output('tube-dropdown', 'value'),
    Input('table_store', 'data'),
    State('IODR_store', 'data'),
    State('tube-dropdown', 'value'))
def update_tube_dropdown(tables_list, device_num, ln_tube):
    table_df = pd.read_json(tables_list[device_num], orient='table')
    newNames = table_df['name']
    try:
        tube_index = newNames[device_num].index(ln_tube) if ln_tube != None else 0
    except:
        tube_index = 0

    return newNames, newNames[tube_index]


# callback for updating the main graph and tube dropdown when a new IODR is loaded
# or the rename tubes button is pressed
@app.callback(
    Output('graph1', 'figure'),
    Input('ODdf_update_store', 'data'),
    Input('table_store', 'data'),
    State('temp_df_store', 'data'),
    State('IODR_store', 'data'),
)
def update_graph(ODdf_update_store, tables_list, temp_df_store, device_num):
    ODdf_update = pd.read_json(ODdf_update_store, orient='table')
    TEMPdf = pd.read_json(temp_df_store, orient='table')
    table_df = pd.read_json(tables_list[device_num], orient='table')

    # make the subplots object
    figure1 = make_subplots(
        rows=3,
        cols=1,
        subplot_titles=("OD data", "OD Log Data", "Temperature"),
        row_heights=[0.4, 0.4, 0.2],
        vertical_spacing=0.1)

    if device_num == 0:
        figure1.update_layout(title="IODR #1")
    elif device_num == 1:
        figure1.update_layout(title="IODR #2")
    elif device_num == 2:
        figure1.update_layout(title="IODR #3")

    index = 0
    # add the traces of each tube
    for col in ODdf_update.columns:
        figure1.add_trace(
            go.Scatter(
                x=ODdf_update.index,
                y=ODdf_update[col],
                mode='markers',
                marker_size=5,
                marker=dict(
                    color=colors[index]
                ),
                name=col,
                meta=col,
                legendgroup=f"{col}",
                # legendgrouptitle_text="OD traces",
                hovertemplate='Time: %{x}' +
                              '<br>OD: %{y}<br>' +
                              'Trace: %{meta}<br>' +
                              '<extra></extra>'),
            row=1,
            col=1)
        index += 1

    index = 0
    for col in ODdf_update.columns:
        figure1.add_trace(
            go.Scatter(
                x=ODdf_update.index,
                y=np.log(ODdf_update[col]),
                mode='markers',
                marker_size=5,
                marker=dict(
                    color=colors[index]
                ),
                name=f"{col} ln",
                legendgroup=f"{col}"
            ),
            row=2,
            col=1
        )
        index += 1

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
            row=3,
            col=1)

    # align the x-axis
    figure1.update_xaxes(matches='x')
    # de-align the y-axes
    figure1.update_yaxes(matches=None)
    # set the range for the temperature y-axis
    figure1.update_yaxes(range=[30, 60], row=3, col=1)
    figure1.update_yaxes(range=[-6, 0], row=2, col=1)
    figure1.update_layout(
        height=1200,
        font=dict(
            family='Open Sans',
            size=15
        ),
        legend_itemdoubleclick='toggleothers',
        legend_groupclick='toggleitem',
        legend_itemsizing='constant',
        # legend_tracegroupgap=320,
        hoverlabel_align='right'
    )
    figure1.update_annotations(font_size=20)
    figure1.update_xaxes(
        title_text="Time",
        row=1,
        col=1
    )
    figure1.update_xaxes(
        title_text="Time",
        row=2,
        col=1
    )
    figure1.update_xaxes(
        title_text="Time",
        row=3,
        col=1
    )
    figure1.update_yaxes(
        title_text="OD",
        row=1,
        col=1
    )
    figure1.update_yaxes(
        title_text="ln OD",
        row=2,
        col=1
    )
    figure1.update_yaxes(
        title_text="Temp (F)",
        row=3,
        col=1
    )
    # return the ODdf_original dataframe as a json to the store component
    return figure1


# callback for the prediction graphs
@app.callback(
    Output('linearODgraph', 'figure'),
    Input('tube-dropdown', 'value'),
    Input('ODdf_update_store', 'data'),
    Input('OD_target_slider', 'value'),
    Input('data-selection-slider', 'value'),
    Input('blank-val-input', 'value'),
    Input('table_store', 'data'),
    State('zoom_vals_store', 'data'),
    State('IODR_store', 'data')
)
def update_predict_graphs(fit_tube, ODdf_update_json, OD_target_slider, data_selection_slider, blank_value_input,
                          tables_list, zoom_vals, device_num):
    # read the dataframe in from the storage component
    ODdf_update = pd.read_json(ODdf_update_json, orient='table')
    table_df = pd.read_json(tables_list[device_num], orient='table')
    names = table_df['name'].tolist()

    try:
        blank_value_input = float(blank_value_input)
    except:
        blank_value_input = 0
    if fit_tube != None:

        # format the data into a dataframe of just the selected tube's OD and lnOD data
        lnODdf = format_ln_data(ODdf_update, names.index(fit_tube),
                                offset_value=float(blank_value_input))
    else:
        lnODdf = format_ln_data(ODdf_update, 0, offset_value=float(blank_value_input))

    # use predict_curve function to predict the curve and get the last time point as a float
    popt, last_time_point = predict_curve(lnODdf, data_selection_slider)

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
            y=lnODdf.lnOD,  # this one?
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

        # create array of y coordinates with linear curve calculated earlier
        y_predict = linear_curve(t_predict, popt[0], popt[1])

        # change the time predict back to datatime objects
        t_predict = (t_predict * pd.Timedelta(1, 'h')) + ODdf_update.index[0]

        r = round(popt[2], 3)
        print("R value:  ", r)
        # add the fit line trace
        predict_figure.add_trace(
            go.Scatter(
                x=t_predict,
                y=y_predict,
                mode='lines',
                name='lnOD prediction',
                meta='lnOD prediction',
                marker=dict(
                    color='green' if r ** 2 > 0.9 else 'red'
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
                y=selection_df.lnOD,  # this one?
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
        # add the ln fit curve trace
        predict_figure.add_trace(
            go.Scatter(
                x=t_predict,
                y=y_predict_lin,
                mode='lines',
                marker=dict(
                    color='green' if r ** 2 > 0.9 else 'red'
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

        predict_figure.add_vline(x=time_intercept_x, line_width=2, line_dash='dash', row=1, col=1)

        time_intercept_x_str = (time_intercept_x).strftime("%Y-%m-%d %H:%M:%S")
        # first_time_str = (first_time_time - pd.Timedelta(4, 'h')).strftime("%Y-%m-%d %H:%M:%S")

        predict_figure.update_annotations(font_size=20)

        predict_figure.add_annotation(
            x=time_intercept_x_str,
            y=OD_target_slider,
            text=f"Time when growth hits target: {time_intercept_x_str}",
            font=dict(
                color="#ffffff",
                size=15
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
    predict_figure.update_layout(legend_tracegroupgap=320, font=dict(size=15, family="Open Sans"))
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
    Output('zoom_vals_store', 'data'),
    Input('linearODgraph', 'relayoutData')
)
def zoom_event(relayout_data):
    data = []
    if relayout_data is not None:
        if 'xaxis.range[0]' in relayout_data:
            data.append(relayout_data['xaxis.range[0]'])
            data.append(relayout_data['xaxis.range[1]'])
        else:
            data = []
        if 'xaxis.autorange' in relayout_data:
            data.append(relayout_data['xaxis.autorange'])
    return data


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)
