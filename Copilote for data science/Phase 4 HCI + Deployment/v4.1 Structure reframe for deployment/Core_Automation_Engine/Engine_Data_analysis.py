import pandas as pd
from Data import filepath
import dash
import time
import pyautogui
from dash import dcc, html, Input, Output, State
import plotly.express as px
import matplotlib.pyplot as plt
import seaborn as sns
import webbrowser
from fpdf import FPDF
import json
import re
from config.api_manager import client, MODEL_NAME

def load_and_preprocess_data():
    data_path = filepath()
    df = pd.read_csv(data_path)
    # Handle missing values by forward filling
    df.fillna(method='ffill', inplace=True)
    return df


class Dashboard:
    def __init__(self):
        self.df = self.load_and_preprocess_data()
        self.config = None
        self.app = dash.Dash(__name__)

    def create_dashboard(self, user_input=None):
        """Creates the initial dashboard layout based on user input"""
        if user_input:
            self.config = self.generate_dashboard_config(user_input, self.df.columns.tolist())
        else:
            self.config = self.default_dashboard_config(self.df.columns.tolist())

        try:
            validated_config = self.validate_config(self.config, self.df.columns)
        except ValueError as e:
            print(f"Invalid configuration: {e}")
            return
        
        # **Interactive Dashboard Layout**
        self.app.layout = html.Div([
            html.H1("Automated Data Dashboard", style={'textAlign': 'center'}),

            # Dropdowns for Interactivity
            html.Div([
                html.Label("Select X-Axis:"),
                dcc.Dropdown(id='x-axis', options=[{'label': col, 'value': col} for col in self.df.columns],
                             value=validated_config["charts"][0]["x"]),

                html.Label("Select Y-Axis:"),
                dcc.Dropdown(id='y-axis', options=[{'label': col, 'value': col} for col in self.df.columns],
                             value=validated_config["charts"][0]["y"]),

                html.Label("Select Chart Type:"),
                dcc.Dropdown(id='chart-type', options=[
                    {'label': 'Bar', 'value': 'bar'},
                    {'label': 'Scatter', 'value': 'scatter'},
                    {'label': 'Histogram', 'value': 'histogram'},
                    {'label': 'Line', 'value': 'line'}
                ], value=validated_config["charts"][0]["type"].lower()),
            ], style={'width': '40%', 'margin': 'auto'}),

            # Graph Output
            dcc.Graph(id='chart-output'),

            html.Div(id='insights-output')
        ])

        # **Add Interactivity with Callbacks**
        @self.app.callback(
            Output('chart-output', 'figure'),
            [Input('x-axis', 'value'),
             Input('y-axis', 'value'),
             Input('chart-type', 'value')]
        )
        def update_chart(x_col, y_col, chart_type):
            return self.create_figure(self.df, {"x": x_col, "y": y_col, "type": chart_type})

        # **Run the App**
        webbrowser.open('http://127.0.0.1:8050/')
        self.app.run_server(debug=True)


    def generate_dashboard_config(self, user_input, available_columns):
        """Generate JSON config using centralized model"""
        
        system_prompt = f"""
        You are an expert Data Dashboard Designer. Convert the user request into a JSON configuration for a dashboard.

        **Context:**
        - Available Columns: {available_columns}
        - User Request: "{user_input}"

        **Rules:**
        1. Return **ONLY** valid JSON.
        2. Keys: "num_charts", "charts".
        3. Chart keys: "type", "x", "y".
        4. "type" must be one of: 'Bar', 'Scatter', 'Histogram', 'Line'.
        5. "x" and "y" must be exact column names from the available columns.
        """
        
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate dashboard config."}
                ],
                temperature=0.3,
                max_tokens=1024
            )
            
            raw_response = response.choices[0].message.content
            match = re.search(r"\{.*\}", raw_response, re.DOTALL)
            if match:
                return json.loads(match.group())
            return self.default_dashboard_config(available_columns)
            
        except Exception as e:
            print(f"Failed to parse JSON response from API: {e}")
            return self.default_dashboard_config(available_columns)

    def validate_config(self, config, df_columns):
        """Validate the configuration against dataset columns"""
        required_keys = {"num_charts", "charts"}
        chart_keys = {"type", "x", "y"}
        
        if not all(key in config for key in required_keys):
            raise ValueError("Missing required configuration keys")
        
        if len(config["charts"]) != config["num_charts"]:
            raise ValueError("Number of charts doesn't match configuration")
        
        for chart in config["charts"]:
            if not all(key in chart for key in chart_keys):
                raise ValueError(f"Missing keys in chart configuration: {chart}")
            if chart["x"] not in df_columns or chart["y"] not in df_columns:
                raise ValueError(f"Invalid column names in chart: {chart}")
        
        return config

    def build_layout_from_config(self, config, df):
        """Build Dash layout from validated configuration"""
        charts = []
        
        for idx, chart_config in enumerate(config["charts"]):
            fig = self.create_figure(df, chart_config)
            charts.append(
                html.Div([
                    html.H3(f"Chart {idx+1}: {chart_config['type']}"),
                    dcc.Graph(figure=fig)
                ], style={'border': '1px solid #ddd', 'padding': '10px', 'margin': '10px'})
            )
        
        return html.Div([
            html.H1("Automated Data Dashboard", style={'textAlign': 'center'}),
            html.Div(charts),
            html.Div(id='insights-output')
        ])

    def create_figure(self, df, chart_config):
        """Creates Plotly figures dynamically based on user selection"""
        chart_type = chart_config["type"].lower()
        x_col = chart_config["x"]
        y_col = chart_config["y"]
        
        if chart_type == "bar":
            return px.bar(df, x=x_col, y=y_col, title=f"{y_col} by {x_col}")
        elif chart_type == "scatter":
            return px.scatter(df, x=x_col, y=y_col, title=f"{y_col} vs {x_col}")
        elif chart_type == "histogram":
            return px.histogram(df, x=x_col, title=f"Distribution of {x_col}")
        elif chart_type == "line":
            return px.line(df, x=x_col, y=y_col, title=f"{y_col} over {x_col}")
        else:
            return px.scatter(df, x=x_col, y=y_col)

    def default_dashboard_config(self, columns):
        """Fallback configuration if API fails"""
        return {
            "num_charts": 2,
            "charts": [
                {"type": "Histogram", "x": columns[0], "y": columns[1]},
                {"type": "Scatter", "x": columns[2], "y": columns[3]}
            ]
        }

    def load_and_preprocess_data(self):
        """Loads and processes the dataset"""
        data_path = filepath()
        df = pd.read_csv(data_path)
        df.fillna(method='ffill', inplace=True)
        return df


class DataAnalysisReport:
    def __init__(self):
        """Initialize with dataset file path."""
        self.file_path = filepath()
        self.df = self.load_data()
    
    def load_data(self):
        """Loads the dataset from a CSV file."""
        try:
            return pd.read_csv(self.file_path)
        except Exception as e:
            print(f"Error loading data: {e}")
            return None

    def generate_insights(self, user_input):
        """Generates insights using dataset statistics and user input."""
        if self.df is None:
            return "No data available for analysis."

        numeric_df = self.df.select_dtypes(include=['number'])
        summary = self.df.describe().to_dict()
        correlation = numeric_df.corr().to_dict()

        stats_json = json.dumps({
            "summary_statistics": summary,
            "correlation_matrix": correlation,
            "column_names": self.df.columns.tolist(),
            "num_rows": self.df.shape[0],
            "num_columns": self.df.shape[1]
        }, indent=4)

        system_prompt = f"""
        You are an expert Data Analyst. Analyze the dataset statistics and provide actionable insights.

        **Context:**
        - User Input: "{user_input}"
        - Statistics (JSON):
        {stats_json}

        **Rules:**
        1. Identify key trends, anomalies, and correlations.
        2. Suggest data-driven actions.
        3. Format the output as a clear, professional report (markdown).
        4. Be concise but impactful.
        """

        insights = self.call_api(system_prompt)
        return insights
    
    def call_api(self, prompt):
        """Calls the API to generate insights."""
        print("\n🔹 API Prompt Sent... calculating insights...")
        
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": "Generate insights."}
                ],
                temperature=0.5,
                max_tokens=4096
            )
            
            raw_response = response.choices[0].message.content.strip()
            print("\n✅ Insights Received.\n")
            return raw_response

        except Exception as e:
            print("\n❌ API Call Failed:", e)
            return "Error: Unable to generate insights due to API failure."

    def generate_pdf_report(self, user_input):
        """Generates a detailed PDF report with insights and graphs."""
        if self.df is None:
            print("No data available for generating report.")
            return

        insights = self.generate_insights(user_input)

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Arial", style='B', size=16)
        pdf.cell(200, 10, "Data Analysis Report", ln=True, align="C")
        pdf.ln(10)
        pdf.set_font("Arial", style='B', size=12)
        pdf.cell(0, 10, "Dataset Summary:", ln=True)
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 6, f"Number of Rows: {self.df.shape[0]}\nNumber of Columns: {self.df.shape[1]}")
        pdf.ln(5)

        if insights:
            pdf.set_font("Arial", style='B', size=12)
            pdf.cell(0, 10, "Insights:", ln=True)
            pdf.set_font("Arial", size=10)
            # FPDF has trouble with utf-8 sometimes, basic handling
            pdf.multi_cell(0, 6, insights.encode('latin-1', 'replace').decode('latin-1'))
            pdf.ln(5)
        else:
            pdf.cell(0, 10, "No insights generated.", ln=True)

        self.add_graphs_to_pdf(pdf)
        output_path = "data_analysis_report.pdf"
        pdf.output(output_path)
        print(f"PDF Report saved to {output_path}")


    def add_graphs_to_pdf(self, pdf):
        """Generates and embeds statistical graphs into the PDF."""
        numeric_df = self.df.select_dtypes(include=['number'])
        if numeric_df.empty:
            print("No numerical columns found for graph generation.")
            return

        temp_images = []
        if len(numeric_df.columns) > 0:
            plt.figure(figsize=(6, 4))
            sns.histplot(numeric_df.iloc[:, 0], bins=20, kde=True, color='blue')
            plt.title(f"Distribution of {numeric_df.columns[0]}")
            plt.xlabel(numeric_df.columns[0])
            plt.ylabel("Frequency")
            hist_path = "histogram.png"
            plt.savefig(hist_path)
            temp_images.append(hist_path)
            plt.close()

        if len(numeric_df.columns) > 1:
            plt.figure(figsize=(6, 4))
            sns.heatmap(numeric_df.corr(), annot=True, cmap="coolwarm", fmt=".2f")
            plt.title("Feature Correlation Heatmap")
            heatmap_path = "correlation_heatmap.png"
            plt.savefig(heatmap_path)
            temp_images.append(heatmap_path)
            plt.close()

        pdf.add_page()
        pdf.set_font("Arial", style='B', size=12)
        pdf.cell(0, 10, "Statistical Graphs:", ln=True)
        for img in temp_images:
            pdf.image(img, x=10, w=180)
            pdf.ln(60)

if __name__ == "__main__":
    report = Dashboard()
    report.create_dashboard("create dashboard of chest pain vs target")
