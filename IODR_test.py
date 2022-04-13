from dash import Dash, dcc, html, Input, Output, State


import numpy as np
import pandas as pd
import urllib.request
import requests
import json
#import time
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
dataFrames = []
# tubeNames = 

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

    df3 = df2.stack().to_frame().reset_index()
    if(i < 3):
        df3.columns = ['time', 'tube', 'OD']
        #df3['lnOD'] = np.log(df3['OD'])
        tubeNames = {
                'field1' : 'LL1004',
                'field2' : 'LL1111',
                'field3' : 'LL1592',
                'field4' : 'LL1590',
                'field5' : 'LL1025',
                'field6' : 'LL1076',
                'field7' : 'LL1049',
                'field8' : 'LL1460'
                }
        df3.tube = df3.tube.replace(tubeNames)
    else:
        df3.columns = ['time', 'sensor', 'temp']
        tempNames = {
            'field1' : 'Dev #1 int',
            'field2' : 'Dev #1 ext',
            'field3' : 'Dev #2 int',
            'field4' : 'Dev #2 ext',
            'field5' : 'Dev #3 int',
            'field6' : 'Dev #3 ext'
            }
        df3.sensor = df3.sensor.replace(tempNames)

    # rename columns based on strain
    
    dataFrames.append(df3)
    # print(devices)


config = {
    'edits': {
        'legendText': True,
        'titleText': True
    }
}


app = Dash(__name__)

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
		    config=config),
		style={'width': '45%', 'float': 'left'}
	),
	html.Div(
	    dcc.Graph(
		    id='graph2',
		    config=config),
	    style={'width': '45%', 'float': 'right'}
	),
	html.Div(
	    dcc.Graph(
		    id='graph3',
		    config=config),
		style={'width': '45%', 'float': 'left'}
	),
	html.Div(
	    dcc.Graph(
	        id='temp-graph',
	        config=config),
	    style={'width': '45%', 'float': 'right'}
	),
	html.Div(
	    dcc.Checklist(['facet row'], id='facet-row-checkbox-1')
	)
])

@app.callback(
    Output('graph1', 'figure'),
    Output('graph2', 'figure'),
    Output('graph3', 'figure'),
    Output('temp-graph', 'figure'),
    Input('facet-row-checkbox-1', 'value'),
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
def update_graph(facet_row_checkbox_1, n_clicks, device_sel, name_1, name_2, name_3, name_4, name_5, name_6, name_7, name_8):
    figure1=px.scatter(dataFrames[0] if device_sel == None else dataFrames[devNames.index(device_sel)],
			x = 'time',
			y = 'OD',
			color = 'tube',
		    title = device_sel,
		    height = 500)
    figure1.update_traces(mode='markers', marker_size=5)
    
    figure2=px.scatter(dataFrames[1],
			x = 'time',
			y = 'OD',
			color = 'tube',
		    title = 'IODR #2 data',
		    facet_row = 'tube' if facet_row_checkbox_1 == ['facet row'] else None,
		    height=900 if facet_row_checkbox_1 == ['facet row'] else 500)
    figure2.update_traces(mode='markers', marker_size=5)
    
    figure3=px.scatter(dataFrames[2],
			x = 'time',
			y = 'OD',
			color = 'tube',
		    title = 'IODR #3 data',
		    facet_row = 'tube' if facet_row_checkbox_1 == ['facet row'] else None,
		    height=900 if facet_row_checkbox_1 == ['facet row'] else 500)
    figure3.update_traces(mode='markers', marker_size=5)
    
    figure4=px.scatter(dataFrames[3],
			x = 'time',
			y = 'temp',
			color = 'sensor',
		    title = 'IODR temp data',
		    facet_row = 'sensor' if facet_row_checkbox_1 == ['facet row'] else None,
		    height=900 if facet_row_checkbox_1 == ['facet row'] else 500)
    figure4.update_traces(mode='markers', marker_size=5)
    
    print("update ", facet_row_checkbox_1)
    return figure1, figure2, figure3, figure4


if __name__ == '__main__':
    app.run_server(debug=True)

