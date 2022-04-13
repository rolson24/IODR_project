from dash import Dash, dcc, html, Input, Output

app = Dash(__name__)

app.layout = html.Div([
    html.H6("Change the value in the text box to see callbacks in action!"),
    html.Div([
        "Input: ",
        dcc.Input(id='my-input', value='initial value', type='text')
    ]),
    html.Br(),
    html.Div(id='my-output'),
    html.Br(),
    html.Label('Radio Items'),
    dcc.RadioItems(id='radio-input', options=['New York City', 'Montréal', 'San Francisco'], value='Montréal'),
    html.Br(),
    html.Div(id='my-output2')

])


@app.callback(
    Output(component_id='my-output', component_property='children'),
	Output(component_id='my-output2', component_property='children'),
	Input(component_id='my-input', component_property='value'),
	Input(component_id='radio-input', component_property='value')
)
def update_output_div(my_input_value, my_radio_value):
    return f'Output: {my_input_value}', f'Output: {my_radio_value}'

if __name__ == '__main__':
    app.run_server(debug=True)
