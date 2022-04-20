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


# set ThingSpeak variables
# 3 sets of data, since there are 3 IODR devices
tsBaseUrl = r'https://api.thingspeak.com/channels'

# IODR device numbers (as of 10-27-2020)
# 1: device in Zeppelin chamber
# 2: device in Montgolfier chamber
# 3: 
# 4: temperature readings for all devices
devNames = ['IODR #1', 'IODR #2', 'IODR #3']
originalNames = ['tube 1', 'tube 2', 'tube 3', 'tube 4', 'tube 5', 'tube 6', 'tube 7', 'tube 8']
newNames = ['field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'field7', 'field8']

dataFrames = []

chIDs = [405675, 441742, 469909, 890567]
readAPIkeys = ['18QZSI0X2YZG8491', 'CV0IFVPZ9ZEZCKA8', '27AE8M5DG8F0ZE44', 'M7RIW6KSSW15OGR1']


def get_OD_data(device, newNames):
    """Returns a data frame containing the OD data for the specified device.
    
    Arguments:
    device -- int device number (0-2)
    newNames -- list of strings for the names of each tube (expected length 8)
    
    relies on global variables chIDs and readAPIkeys
    """
    # select the channel ID and read API key depending on which device is being used
    #chID = chIDs[devNum-1]
    chID = chIDs[device]

    #readAPIkey = readAPIkeys[devNum-1]
    readAPIkey = readAPIkeys[device]

    # get data from Thingspeak
    myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?results=8000'.format(channel_id = chID)
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

    # rename tubes on update
    i=0;
    for col in df2.columns:
        df.rename(columns = {col : newNames[i]}, inplace = True)
        i += 1
    
    return df2


def get_temp_data(device):
    """Returns a data frame containing the temperature data for the specified device
    
    Arguments:
    device -- int device number (0-2)
    
    relies on global variables chIDs and readAPIkeys
    """
    # select the channel ID and read API key depending on which device is being used
    #chID = chIDs[devNum-1]
    chID = chIDs[3]

    #readAPIkey = readAPIkeys[devNum-1]
    readAPIkey = readAPIkeys[3]

    # get data from Thingspeak
    myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?results=8000'.format(channel_id = chID)
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


app = Dash(__name__)

server = app.server

# for heroku server
server.wsgi_app = WhiteNoise(server.wsgi_app, root='static/c')

app.layout = html.Div([
    html.H1("IODR Data Browser", style={'textAlign': 'center'}),
    # get data button
    html.Div(
        children=[
	        html.Button(
	            'IODR #1',
	            id='IODR1-button',
	            style={
	                'flex': 1,
	                'marginLeft': '50%',
	                'marginTop': 15
	            }
	        ),
	        html.Button(
	            'IODR #2',
	            id='IODR2-button',
	            style={
	                'flex': 1,
	                'marginLeft': '50%',
	                'marginTop': 15
	            }
	        ),
	        html.Button(
	            'IODR #3',
	            id='IODR3-button',
	            style={
	                'flex': 1,
	                'marginLeft': '50%',
	                'marginTop': 15
	            }
	        )
	    ],
	    style={
	        'flex': 1,
	        'width': '30%',
	        'height': 100,
	        'float': 'left',
	        'marginTop': 50
	    }
	),
	# device selector dropdown
	# table to input tube names
	html.Div(children=[
	    html.Div(children=[
	        html.Label('Tube')],
	        className='tube-title'
	    ),
	    
	    html.Div(children=[
	        html.Label('Name')],
	        className='name-title'
	    ),
	    
	    html.Div(children=[
	        html.Label('1')],
	        className='tube-num-label'
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-1-name')],
	        className='tube-input'
	    ),
	    
	    html.Div(children=[
	        html.Label('2')],
	        className='tube-num-label'
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-2-name')],
	        className='tube-input'
	    ),
	    
	    html.Div(children=[
	        html.Label('3')],
	        className='tube-num-label'
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-3-name')],
	        className='tube-input'
	    ),
	    
	    html.Div(children=[
	        html.Label('4')],
	        className='tube-num-label'
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-4-name')],
	        className='tube-input'
	    ),
	    
	    html.Div(children=[
	        html.Label('5')],
	        className='tube-num-label'
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-5-name')],
	        className='tube-input'
	    ),
	    
	    html.Div(children=[
	        html.Label('6')],
	        className='tube-num-label'
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-6-name')],
	        className='tube-input'
	    ),
	    
	    html.Div(children=[
	        html.Label('7')],
	        className='tube-num-label'
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-7-name')],
	        className='tube-input'
	    ),
	    html.Div(children=[
	        html.Label('8')],
	        className='tube-num-label'
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-8-name')],
	        className='tube-input'
	    )
	    ],
	    style={
	        'padding': 10,
	        'flex': 1,
	        'width': '30%',
	        'height': 200,
	        'marginLeft': '50%'
	    }
	),
	html.Br(),
	# graph html component
	html.Div(
	    dcc.Graph(
	        id='graph1')
	),
	html.H3("Instructions for use:", style={'textAlign': 'center'}),
	html.Br(),
	html.Div(
	    '''
	    To use this dashboard, first input the names of the bateria strains that 
	    correspond to each tube. Then click the button labeled with the device you want
	    to view data from. Doing so will pull the most recent 8000 data points
	    (1000 per tube) and display them on the scatter plot. To zoom in on a set of
	    points, simply click and drag on the graph and a selection box will appear
	    showing the frame that will be zoomed to. To zoom back out, double click on 
	    the graph and the graph will return to the original view. You can also move the 
	    graph horizontally and vertically by clicking and dragging on the labels of the 
	    axes. To turn individual traces off and on, click the name in the legend of the 
	    graph. To turn all the traces off but one, double click on the trace you want on.
	    ''', style={'marginLeft': 30, 'marginRight': 30, 'marginBottom': 30})
])

@app.callback(
    Output('graph1', 'figure'),
    Input('IODR1-button', 'n_clicks'),
    Input('IODR2-button', 'n_clicks'),
    Input('IODR3-button', 'n_clicks'),
    State('tube-1-name', 'value'),
    State('tube-2-name', 'value'),
    State('tube-3-name', 'value'),
    State('tube-4-name', 'value'),
    State('tube-5-name', 'value'),
    State('tube-6-name', 'value'),
    State('tube-7-name', 'value'),
    State('tube-8-name', 'value'))
def update_graph(IODR1_button, IODR2_button, IODR3_button, name_1, name_2, name_3, name_4, name_5, name_6, name_7, name_8):
    # put the new names into the list 
    newNames[0] = name_1 if (name_1 != None and name_1 != "") else originalNames[0]
    newNames[1] = name_2 if (name_2 != None and name_2 != "") else originalNames[1]
    newNames[2] = name_3 if (name_3 != None and name_3 != "") else originalNames[2]
    newNames[3] = name_4 if (name_4 != None and name_4 != "") else originalNames[3]
    newNames[4] = name_5 if (name_5 != None and name_5 != "") else originalNames[4]
    newNames[5] = name_6 if (name_6 != None and name_6 != "") else originalNames[5]
    newNames[6] = name_7 if (name_7 != None and name_7 != "") else originalNames[6]
    newNames[7] = name_8 if (name_8 != None and name_8 != "") else originalNames[7]
    
    # make the subplots object
    figure1 = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("OD data", "Temperature"),
        row_heights=[0.8, 0.2],
        vertical_spacing = 0.08)
    # checks which button was pressed
    changed_id = [p['prop_id'] for p in callback_context.triggered][0]
    if 'IODR1-button' in changed_id:
        device = 0
        figure1.update_layout(title="IODR #1")
    elif 'IODR2-button' in changed_id:
        device = 1
        figure1.update_layout(title="IODR #2")
    elif 'IODR3-button' in changed_id:
        device = 2
        figure1.update_layout(title="IODR #3")
    else:
        device = 0
        figure1.update_layout(title="IODR #1")
    
    # retrieve the data from Thingspeak
    ODdf = get_OD_data(device, newNames)
    TEMPdf = get_temp_data(device)
    
    # add the traces of each tube
    for col in ODdf.columns:
        figure1.add_trace(
            go.Scattergl(
                x=ODdf.index,
                y=ODdf[col],
                mode='markers',
                marker_size=5,
                name=col),
            row = 1,
            col = 1)
    # add the traces of the temperature
    for col in TEMPdf.columns:
        figure1.add_trace(
            go.Scattergl(
                x=TEMPdf.index,
                y=TEMPdf[col],
                mode='markers',
                marker_size=5,
                name=col), 
            row = 2,
            col = 1)
    
    # align the x-axis
    figure1.update_xaxes(matches='x')
    # de-align the y-axes
    figure1.update_yaxes(matches=None)
    # set the range for the temperature y-axis
    figure1.update_yaxes(range=[30, 60], row=2, col=1)
    figure1.update_layout(
        height=1000,
        font=dict(
            family='Open Sans',
            size=14))

    return figure1


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)

