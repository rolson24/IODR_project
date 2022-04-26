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


def get_OD_data(device):
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
    myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?results=1500'.format(channel_id = chID)
    #myUrl = 'https://api.thingspeak.com/channels/{channel_id}/feeds.csv?start=2021-09-20'.format(channel_id = chID)
    # print(myUrl)
    r = requests.get(myUrl)

    # put the thingspeak data in a dataframe
    df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))

    df2 = df.drop('entry_id', axis = 'columns')

    # convert time string to datetime, and switch from UTC to Eastern time
    df2['time'] = pd.to_datetime(df2['created_at']).dt.tz_convert('US/Eastern')
    df2 = df2.drop('created_at', axis = 'columns')
    df2.set_index('time', inplace = True)

    return df2

def rename_tubes(dataframe, newNames):
    # rename tubes on update
    i=0;
    for col in dataframe.columns:
        dataframe.rename(columns = {col : newNames[i]}, inplace = True)
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
	html.Div(
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
	# device selector dropdown
	# table to input tube names
	html.Div(children=[
		html.Table(children=[
			html.Thead(children=[
				html.Tr(children=[
					html.Th(children="Tube", scope='col'),
					html.Th(children="Name", scope='col', className='name-title')
				])
			]),
			html.Tbody(children=[
				html.Tr(children=[
					html.Th('1', scope='row', className='tube-num-input'),
					html.Td(
						dcc.Input(id='tube-1-name'),
						className='tube-input'
					)
				]),
				html.Tr(children=[
					html.Th('2', scope='row', className='tube-num-input'),
					html.Td(
						dcc.Input(id='tube-2-name'),
						className='tube-input'
					)
				]),
				html.Tr(children=[
					html.Th('3', scope='row', className='tube-num-input'),
					html.Td(
						dcc.Input(id='tube-3-name'),
						className='tube-input'
					)
				]),
				html.Tr(children=[
					html.Th('4', scope='row', className='tube-num-input'),
					html.Td(
						dcc.Input(id='tube-4-name'),
						className='tube-input'
					)
				]),
				html.Tr(children=[
					html.Th('5', scope='row', className='tube-num-input'),
					html.Td(
						dcc.Input(id='tube-5-name'),
						className='tube-input'
					)
				]),
				html.Tr(children=[
					html.Th('6', scope='row', className='tube-num-input'),
					html.Td(
						dcc.Input(id='tube-6-name'),
						className='tube-input'
					)
				]),
				html.Tr(children=[
					html.Th('7', scope='row', className='tube-num-input'),
					html.Td(
						dcc.Input(id='tube-7-name'),
						className='tube-input'
					)
				]),
				html.Tr(children=[
					html.Th('8', scope='row', className='tube-num-input'),
					html.Td(
						dcc.Input(id='tube-8-name'),
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
	html.H2("Instructions for use:", style={'textAlign': 'center'}),
	html.Br(),
	html.Div(children=[
	    '''
	    To use this dashboard, first click the button labeled with the device you want 
	    to view data from. Doing so will pull the most recent 8000 data points 
	    (1000 per tube) and display them on the scatter plot. This process takes about 
	    3 seconds to display the graph Note, this data does not update in real-time. 
	    In order to see the latest data, click the device button again.''',
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
	    style={'marginLeft': 30, 'marginRight': 30, 'marginBottom': 30})
])

@app.callback(
    Output('graph1', 'figure'),
    Input('IODR1-button', 'n_clicks'),
    Input('IODR2-button', 'n_clicks'),
    Input('IODR3-button', 'n_clicks'),
    Input('rename-button', 'n_clicks'),
    State('tube-1-name', 'value'),
    State('tube-2-name', 'value'),
    State('tube-3-name', 'value'),
    State('tube-4-name', 'value'),
    State('tube-5-name', 'value'),
    State('tube-6-name', 'value'),
    State('tube-7-name', 'value'),
    State('tube-8-name', 'value'))
def update_graph(IODR1_button, IODR2_button, IODR3_button, rename_button, name_1, name_2, name_3, name_4, name_5, name_6, name_7, name_8):
    # put the new names into the list 
    newNames[0] = name_1 if (name_1 != None and name_1 != "") else originalNames[0]
    newNames[1] = name_2 if (name_2 != None and name_2 != "") else originalNames[1]
    newNames[2] = name_3 if (name_3 != None and name_3 != "") else originalNames[2]
    newNames[3] = name_4 if (name_4 != None and name_4 != "") else originalNames[3]
    newNames[4] = name_5 if (name_5 != None and name_5 != "") else originalNames[4]
    newNames[5] = name_6 if (name_6 != None and name_6 != "") else originalNames[5]
    newNames[6] = name_7 if (name_7 != None and name_7 != "") else originalNames[6]
    newNames[7] = name_8 if (name_8 != None and name_8 != "") else originalNames[7]
    # print(newNames)
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
    ODdf = get_OD_data(device)
    TEMPdf = get_temp_data(device)
    
    if 'rename-button' in changed_id:
        rename_tubes(ODdf, newNames)
    
    # add the traces of each tube
    for col in ODdf.columns:
        figure1.add_trace(
            go.Scatter(
                x=ODdf.index,
                y=ODdf[col],
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

    return figure1


if __name__ == '__main__':
    app.run_server(debug=True, host='0.0.0.0', port=8050)

