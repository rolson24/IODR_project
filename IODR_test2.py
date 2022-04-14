from dash import Dash, dcc, html, Input, Output, State
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

for i in range(4):
    # select the channel ID and read API key depending on which device is being used
    #chID = chIDs[devNum-1]
    chID = chIDs[i]

    #readAPIkey = readAPIkeys[devNum-1]
    readAPIkey = readAPIkeys[i]

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
    dataFrames.append(df2)

def get_OD_data(device, newNames):
    df = dataFrames[device]
    # rename tubes on update
    tubeNamesDict = {}
    i=0;
    for col in df.columns:
        df.rename(columns = {col : newNames[i]}, inplace = True)
        i += 1
    
    return df


def get_temp_data(device):
    df = dataFrames[3]
    # format data for temperature, inlcude only temperature that matches the device selected
    if(device == 0):
        df2 = df.drop(['field3', 'field4', 'field5', 'field6'], axis = 'columns')
    elif (device == 1):
        df2 = df.drop(['field1', 'field2', 'field5', 'field6'], axis = 'columns')
    else:
        df2 = df.drop(['field1', 'field2', 'field3', 'field4'], axis = 'columns')
    
    # rename columns for graphing
    tempNames = {
           'field1' : 'Temp Int',
           'field2' : 'Temp Ext',
           'field3' : 'Temp Int',
           'field4' : 'Temp Ext',
           'field5' : 'Temp Int',
           'field6' : 'Temp Ext'
           }
    df2.rename(columns = tempNames, inplace=True)
    
    return df2

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
    html.Div(children=[
	    html.Button(
	        'Get Data',
	        id='get-data-button',
	        style={
	            'flex': 1,
	            'marginLeft': '50%'}
	        )],
	    style={
	        'flex': 1,
	        'width': '30%',
	        'height': 100,
	        'float': 'right',
	        'marginTop': 50}
	),
	# device selector dropdown
	html.Div(children=[
	    html.Label('Device'),
	    dcc.Dropdown(devNames, id='device-selector')],
	    style={
	        'padding': 10,
	        'flex': 1,
	        'textAlign': 'center',
	        'width': '30%',
	        'height': 100,
	        'float': 'left'
	    }
	),
	# table to input tube names
	html.Div(children=[
	    html.Div(children=[
	        html.Label('Tube')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'left', 'textAlign': 'center'}
	    ),
	    html.Div(children=[
	        html.Label('Name')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'right'}
	    ),
	    
	    html.Div(children=[
	        html.Label('1')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'left', 'textAlign': 'center'}
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-1-name')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'right'}
	    ),
	    
	    html.Div(children=[
	        html.Label('2')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'left', 'textAlign': 'center'}
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-2-name')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'right'}
	    ),
	    
	    html.Div(children=[
	        html.Label('3')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'left', 'textAlign': 'center'}
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-3-name')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'right'}
	    ),
	    
	    html.Div(children=[
	        html.Label('4')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'left', 'textAlign': 'center'}
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-4-name')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'right'}
	    ),
	    
	    html.Div(children=[
	        html.Label('5')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'left', 'textAlign': 'center'}
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-5-name')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'right'}
	    ),
	    
	    html.Div(children=[
	        html.Label('6')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'left', 'textAlign': 'center'}
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-6-name')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'right'}
	    ),
	    
	    html.Div(children=[
	        html.Label('7')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'left', 'textAlign': 'center'}
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-7-name')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'right'}
	    ),
	    html.Div(children=[
	        html.Label('8')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'left', 'textAlign': 'center'}
	    ),
	    html.Div(children=[
	        dcc.Input(id='tube-8-name')],
	        style={'flex': 1, 'width': '48%', 'height': 20, 'float': 'right'}
	    )
	    ],
	    style={
	        'padding': 10,
	        'flex': 1,
	        'width': '30%',
	        'height': 200,
	        'marginLeft': '33%'
	    }
	),
	html.Br(),
	# graph html component
	html.Div(
	    dcc.Graph(
	        id='graph1')
	)
])

@app.callback(
    Output('graph1', 'figure'),
    Input('get-data-button', 'n_clicks'),
    State('device-selector', 'value'),
    State('tube-1-name', 'value'),
    State('tube-2-name', 'value'),
    State('tube-3-name', 'value'),
    State('tube-4-name', 'value'),
    State('tube-5-name', 'value'),
    State('tube-6-name', 'value'),
    State('tube-7-name', 'value'),
    State('tube-8-name', 'value'))
def update_graph(n_clicks, device_sel, name_1, name_2, name_3, name_4, name_5, name_6, name_7, name_8):
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
    
    # default data with no device selected
    if device_sel is None:
        ODdf = get_OD_data(0, newNames)
        TEMPdf = get_temp_data(0)
        figure1.update_layout(title="IODR #1")
    # selected device data
    else:
        ODdf = get_OD_data(devNames.index(device_sel), newNames)
        TEMPdf = get_temp_data(devNames.index(device_sel))
        figure1.update_layout(title=device_sel)
    
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
    # disalign the y-axes
    figure1.update_yaxes(matches=None)
    # set the range for the temperature y-axis
    figure1.update_yaxes(range=[30, 60], row=2, col=1)
    figure1.update_layout(
        height=1000,
        font_family='Open Sans')

    return figure1


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)

