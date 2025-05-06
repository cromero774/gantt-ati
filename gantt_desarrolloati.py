import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output, callback_context, State
import requests
import sys
from datetime import datetime
import time

# --- Función de debug ---
def debug_print(message):
    pass  # Desactivado para entorno de producción

# --- Función para cargar datos ---
def cargar_datos():
    sheet_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vT6s9qMzmA_sJRko5EDggumO4sybGVq3n-uOmZOMj8CJDnHo9AWZeZOXZGz7cTg4XoqeiPDIgQP3QER/pub?output=csv"
    
    try:
        response = requests.get(sheet_url, timeout=15)
        response.raise_for_status()
        df = pd.read_csv(sheet_url, encoding='utf-8')
        df.columns = df.columns.str.strip()
        df['RN'] = df['RN'].astype(str).str.strip()
        for col in ['Inicio', 'Fin']:
            try:
                df[col] = pd.to_datetime(df[col], format='%d/%m/%Y', errors='coerce')
            except:
                try:
                    df[col] = pd.to_datetime(df[col], format='%d-%m-%Y', errors='coerce')
                except:
                    try:
                        df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
                    except Exception:
                        pass
        df = df.dropna(subset=['Inicio', 'Fin'])
        df['Inicio_str'] = df['Inicio'].dt.strftime('%d-%m-%Y')
        df['Fin_str'] = df['Fin'].dt.strftime('%d-%m-%Y')
        df['Duracion'] = (df['Fin'] - df['Inicio']).dt.days
        df['Mes'] = df['Fin'].dt.to_period('M').astype(str)
        df['RN_trunc'] = df['RN'].str.lower().apply(lambda x: x if len(x) <= 30 else x[:27] + '...')
        return df, None
    except Exception as e:
        sample_dates = pd.date_range(start='2023-01-01', periods=3)
        df = pd.DataFrame({
            'RN': ['Error - Sin datos', 'Ejemplo 2', 'Ejemplo 3'],
            'Estado': ['Error', 'Error', 'Error'],
            'Inicio': sample_dates,
            'Fin': sample_dates + pd.Timedelta(days=30),
        })
        df['Inicio_str'] = df['Inicio'].dt.strftime('%d-%m-%Y')
        df['Fin_str'] = df['Fin'].dt.strftime('%d-%m-%Y')
        df['Duracion'] = 30
        df['Mes'] = df['Fin'].dt.to_period('M').astype(str)
        df['RN_trunc'] = df['RN'].str.lower()
        return df, str(e)

# --- Cargar datos iniciales ---
df, error_inicial = cargar_datos()
ultima_actualizacion = datetime.now()

# --- Colores por estado ---
color_estado = {
    'Entregado': '#2ecc71',
    'En desarrollo': '#1abc9c',
    'Backlog': '#f1c40f',
    'Para refinar': '#f5d76e',
    'Escribiendo': '#e67e22',
    'Para escribir': '#e74c3c',
    'En Análisis': '#9b59b6',
    'Cancelado': '#95a5a6',
    'Error': '#e74c3c'
}

# --- App Dash ---
app = Dash(__name__)
server = app.server

# --- Layout ---
app.layout = html.Div([
    html.H1("Gantt desarrollo ATI", style={'textAlign': 'center'}),
    html.Div([
        html.Div([
            html.Label("Mes de entrega:"),
            dcc.Dropdown(
                id='mes-dropdown',
                options=[{'label': 'Todos', 'value': 'Todos'}] +
                        [{'label': mes, 'value': mes} for mes in sorted(df['Mes'].unique())],
                value='Todos',
                clearable=False
            )
        ], style={'width': '30%', 'display': 'inline-block'}),
        html.Div([
            html.Label("Estado:"),
            dcc.Dropdown(
                id='estado-dropdown',
                options=[{'label': 'Todos', 'value': 'Todos'}] +
                        [{'label': estado, 'value': estado} for estado in sorted(df['Estado'].unique())],
                value='Todos',
                clearable=False
            )
        ], style={'width': '30%', 'display': 'inline-block', 'marginLeft': '10px'}),
        html.Div([
            html.Label("Tema:"),
            dcc.RadioItems(
                id='theme-switch',
                options=[
                    {'label': 'Claro', 'value': 'light'},
                    {'label': 'Oscuro', 'value': 'dark'}
                ],
                value='light',
                labelStyle={'display': 'inline-block', 'marginRight': '10px'}
            )
        ], style={'width': '30%', 'display': 'inline-block', 'marginLeft': '10px'}),
    ], style={'marginBottom': '20px'}),

    html.Div([
        html.Button('Actualizar datos', id='refresh-button', 
                   style={'backgroundColor': '#3498db', 'color': 'white', 
                          'border': 'none', 'padding': '10px 15px', 
                          'borderRadius': '4px', 'cursor': 'pointer',
                          'marginRight': '15px'}),
        dcc.Interval(
            id='interval-component',
            interval=60*1000*5,  # Actualizar cada 5 minutos (en milisegundos)
            n_intervals=0
        ),
        html.Span(id='ultima-actualizacion', 
                 style={'fontStyle': 'italic', 'fontSize': '0.9em'}),
        html.Span(id='error-mensaje', 
                 style={'color': 'red', 'marginLeft': '15px', 'fontWeight': 'bold'})
    ], style={'marginBottom': '15px'}),

    html.Div([
        dcc.Graph(id='gantt-graph', style={'height': '80vh'})
    ]),
    
    # Store para almacenar datos
    dcc.Store(id='store-data'),
    dcc.Store(id='store-timestamp')
])

# --- Callback para actualizar datos ---
@app.callback(
    [Output('store-data', 'data'),
     Output('store-timestamp', 'data'),
     Output('ultima-actualizacion', 'children'),
     Output('error-mensaje', 'children'),
     Output('mes-dropdown', 'options'),
     Output('estado-dropdown', 'options')],
    [Input('refresh-button', 'n_clicks'),
     Input('interval-component', 'n_intervals')],
    [State('mes-dropdown', 'value'),
     State('estado-dropdown', 'value')]
)
def actualizar_datos(n_clicks, n_intervals, mes_actual, estado_actual):
    global df, ultima_actualizacion
    
    # Cargar datos frescos
    df_new, error = cargar_datos()
    
    # Actualizar timestamp
    ultima_actualizacion = datetime.now()
    timestamp_str = ultima_actualizacion.strftime("%d-%m-%Y %H:%M:%S")
    
    # Preparar opciones para los dropdowns
    mes_options = [{'label': 'Todos', 'value': 'Todos'}] + [
        {'label': mes, 'value': mes} for mes in sorted(df_new['Mes'].unique())
    ]
    
    estado_options = [{'label': 'Todos', 'value': 'Todos'}] + [
        {'label': estado, 'value': estado} for estado in sorted(df_new['Estado'].unique())
    ]
    
    # Guardar los datos actualizados
    df = df_new
    
    # Mensaje de última actualización
    ultima_act_msg = f"Última actualización: {timestamp_str}"
    
    # Mensaje de error (si existe)
    error_msg = f"Error: {error}" if error else ""
    
    return df.to_dict('records'), timestamp_str, ultima_act_msg, error_msg, mes_options, estado_options

# --- Callback para actualizar el gráfico ---
@app.callback(
    Output('gantt-graph', 'figure'),
    [Input('store-data', 'data'),
     Input('mes-dropdown', 'value'),
     Input('estado-dropdown', 'value'),
     Input('theme-switch', 'value')]
)
def actualizar_grafico(data, mes, estado, theme):
    if data:
        df_filtrado = pd.DataFrame(data)
        # Convertir columnas de fecha de nuevo a datetime
        for col in ['Inicio', 'Fin']:
            df_filtrado[col] = pd.to_datetime(df_filtrado[col])
    else:
        df_filtrado = df.copy()
    
    if mes != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['Mes'] == mes]
    if estado != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['Estado'] == estado]

    if df_filtrado.empty:
        return px.scatter(title="Sin datos con los filtros seleccionados")

    if theme == 'dark':
        plot_bgcolor = '#23272f'
        paper_bgcolor = '#23272f'
        font_color = '#f0f0f0'
        gridcolor = '#444'
        fecha_actual_color = 'rgba(255, 255, 255, 0.15)'  # Color muy sutil para fecha actual en tema oscuro
        fecha_text_color = '#e2e8f0'
    else:
        plot_bgcolor = 'white'
        paper_bgcolor = 'white'
        font_color = '#222'
        gridcolor = '#eee'
        fecha_actual_color = 'rgba(66, 153, 225, 0.15)'  # Color muy sutil para fecha actual en tema claro
        fecha_text_color = '#3182ce'

    df_filtrado = df_filtrado.sort_values('Inicio')
    rn_order = df_filtrado['RN_trunc'].unique().tolist()
    df_filtrado['RN_order'] = df_filtrado['RN_trunc'].map({rn: i for i, rn in enumerate(rn_order)})
    df_filtrado = df_filtrado.sort_values('RN_order')

    try:
        fig = px.timeline(
            df_filtrado,
            x_start="Inicio",
            x_end="Fin",
            y="RN_trunc",
            color="Estado",
            custom_data=["RN", "Inicio_str", "Fin_str", "Duracion"],
            color_discrete_map=color_estado,
            title=f"ATI - {estado if estado != 'Todos' else 'Todos los estados'} | {mes if mes != 'Todos' else 'Todos los meses'}"
        )

        fig.update_traces(
            hovertemplate="<b>%{customdata[0]}</b><br>Inicio: %{customdata[1]}<br>Fin: %{customdata[2]}<br>Duración: %{customdata[3]} días",
            marker=dict(line=dict(width=0.3, color='DarkSlateGrey'))
        )

        # Obtener la fecha actual
        fecha_actual = datetime.now()
        
        # Formatear fecha para mostrar en la anotación
        fecha_actual_str = fecha_actual.strftime('%d-%m-%Y')
        
        # Añadir un área sombreada muy sutil para la fecha actual
        fig.add_shape(
            type="rect",
            x0=fecha_actual,
            x1=fecha_actual + pd.Timedelta(hours=3),  # Un ancho apenas perceptible
            y0=-0.5,
            y1=len(rn_order),
            xref="x",
            yref="y",
            fillcolor=fecha_actual_color,
            opacity=0.6,
            layer="below",
            line_width=0
        )
        
        # Añadir una anotación más discreta para la fecha actual
        fig.add_annotation(
            x=fecha_actual,
            y=len(rn_order) + 0.5,  # Colocar en la parte superior
            text=f"Hoy: {fecha_actual_str}",
            showarrow=False,
            yshift=5,
            xshift=0,
            xanchor="center",
            yanchor="bottom",
            font=dict(color=fecha_text_color, size=9),
            opacity=0.9
        )

        fig.update_layout(
            xaxis=dict(title="Fecha", tickformat="%d-%m-%Y", gridcolor=gridcolor),
            yaxis=dict(
                autorange="reversed", 
                title="Requerimiento",
                categoryorder='array',
                categoryarray=rn_order,
                tickfont=dict(size=11),
                title_font=dict(size=13)
            ),
            plot_bgcolor=plot_bgcolor,
            paper_bgcolor=paper_bgcolor,
            font=dict(color=font_color),
            legend=dict(title="Estado", x=1.01, y=1),
            margin=dict(l=20, r=250, t=50, b=50),
            height=max(400, 25 * len(df_filtrado))
        )

        return fig

    except Exception as e:
        return px.scatter(title=f"Error al generar gráfico: {e}")

# --- Ejecutar ---
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)


































































