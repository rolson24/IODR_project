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
oldNames = ['field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'field7', 'field8']
newNames = ['field1', 'field2', 'field3', 'field4', 'field5', 'field6', 'field7', 'field8']

chIDs = [405675, 441742, 469909, 890567]
readAPIkeys = ['18QZSI0X2YZG8491', 'CV0IFVPZ9ZEZCKA8', '27AE8M5DG8F0ZE44', 'M7RIW6KSSW15OGR1']


def get_OD_data(device, newNames, oldNames):
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

    #display(df.head())
    df2 = df.drop('entry_id', axis = 'columns')
    #df2 = df.drop('field8', axis = 'columns')
    #df2 = df
    #display(df2[:5])
    #display(df2.head())

    # convert time string to datetime, and switch from UTC to Eastern time
    df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    df2 = df2.drop('created_at', axis = 'columns')
    df2.set_index('time', inplace = True)
    #display(df2[:5])

    #df3 = df2.stack().to_frame().reset_index()
    #df3.columns = ['time', 'tube', 'OD']
    #df3['lnOD'] = np.log(df3['OD'])
    tubeNamesDict = {}
    df2Columns = list(df2.columns)
    for i in range(len(newNames)):
        df2.rename(columns = {oldNames[i] : newNames[i]}, inplace = True)
        tubeNamesDict[oldNames[i]] = newNames[i]
    #df3.tube = df3.tube.replace(tubeNamesDict)
    return df2


def get_temp_data(device):
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

    #display(df.head())
    df2 = df.drop('entry_id', axis = 'columns')
    #df2 = df.drop('field8', axis = 'columns')
    #df2 = df
    #display(df2[:5])
    #display(df2.head())

    # convert time string to datetime, and switch from UTC to Eastern time
    df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    df2 = df2.drop('created_at', axis = 'columns')
    df2.set_index('time', inplace = True)
    if(device == 0):
        df3 = df2.drop(['field3', 'field4', 'field5', 'field6'], axis = 'columns')
    elif (device == 1):
        df3 = df2.drop(['field1', 'field2', 'field5', 'field6'], axis = 'columns')
    else:
        df3 = df2.drop(['field1', 'field2', 'field3', 'field4'], axis = 'columns')

    #df4 = df3.stack().to_frame().reset_index()
    #df4.columns = ['time', 'sensor', 'temp']
    tempNames = {
           'field1' : 'Dev #1 int',
           'field2' : 'Dev #1 ext',
           'field3' : 'Dev #2 int',
           'field4' : 'Dev #2 ext',
           'field5' : 'Dev #3 int',
           'field6' : 'Dev #3 ext'
           }
    df3.rename(columns = tempNames, inplace=True)
    # need to write the part for the correct device
    return df3

config = {
    'edits': {
        'legendText': True,
        'titleText': True
    }
}


app = Dash(__name__)

server = app.server

server.wsgi_app = WhiteNoise(server.wsgi_app, root='static/c')

app.layout = html.Div([
    html.Div(children=[
	    html.Button('Get Data', id='get-data-button', style={'flex': 1, 'marginLeft': 30})],
	    style={'flex': 1, 'width': '30%', 'height': 100, 'float': 'right', 'marginTop': 50}
	),
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
	html.Div(
	    dcc.Graph(
	        id='graph1',
	        config=config)
	)# ,
	# html.Br(),
# 	html.Div(
# 	   dcc.Graph(
# 	       id='temp-graph',
# 	       config=config)
# 	)"""
])

@app.callback(
    Output('graph1', 'figure'),
    #Output('temp-graph', 'figure'),
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
    oldNames = newNames.copy()
    newNames[0] = name_1 if name_1 is not None else newNames[0]
    newNames[1] = name_2 if name_2 is not None else newNames[1]
    newNames[2] = name_3 if name_3 is not None else newNames[2]
    newNames[3] = name_4 if name_4 is not None else newNames[3]
    newNames[4] = name_5 if name_5 is not None else newNames[4]
    newNames[5] = name_6 if name_6 is not None else newNames[5]
    newNames[6] = name_7 if name_7 is not None else newNames[6]
    newNames[7] = name_8 if name_8 is not None else newNames[7]

    figure1 = make_subplots(rows=2, cols=1, subplot_titles=("OD data", "Temperature"), row_heights=[0.7, 0.3])
    if device_sel is None:
        ODdf = get_OD_data(0, newNames, oldNames)
        TEMPdf = get_temp_data(0)
        figure1.update_layout(title="IODR #1")
    else:
        ODdf = get_OD_data(devNames.index(device_sel), newNames, oldNames)
        TEMPdf = get_temp_data(devNames.index(device_sel))
        figure1.update_layout(title=device_sel)
    ODdfcolumns = list(ODdf.columns) # figure out 
    TEMPdfcolumns = list(TEMPdf.columns)
    for i in range(8):
        figure1.add_trace(go.Scatter(x=ODdf.index, y=ODdf.iloc[:, i], mode='markers', marker_size=2, name=ODdfcolumns[i]), 1, 1)
    for i in range(2):
        figure1.add_trace(go.Scatter(x=TEMPdf.index, y=TEMPdf.iloc[:, i], mode='markers', marker_size=2, name=TEMPdfcolumns[i]), 2, 1)
    figure1.update_xaxes(matches='x')
    figure1.update_layout(height=600)
    # figure1=px.scatter(get_OD_data(0, newNames, oldNames) if device_sel is None else get_OD_data(devNames.index(device_sel), newNames, oldNames),
#             x = 'time',
#             y = 'OD',
#             color = 'tube',
#             title = 'IODR #1' if device_sel is None else device_sel,
#             height = 500)
#     figure1.update_traces(mode='markers', marker_size=5)
#     figure1.add_trace(go.Scatter(get_temp_data(0)))
#     figure4=px.scatter(get_temp_data(0) if device_sel is None else get_temp_data(devNames.index(device_sel)),
#             x = 'time',
#             y = 'temp',
#             color = 'sensor',
#             title = 'IODR temp data',
#             height = 300)
#     figure4.update_traces(mode='markers', marker_size=5)
    
    return figure1 #, figure4


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)

