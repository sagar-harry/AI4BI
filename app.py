from flask import Flask,render_template, request, flash, redirect, url_for
import os,shutil
from werkzeug.utils import secure_filename
from markupsafe import escape
import pandas as pd
from geminiAi import generate_kpi,generate_chart
import json
import re
from charts import bar_chart, line_chart, scatter_chart


file_storage_folder='/Users/vinayakmoudgil/Documents/my_work/Projects_vinni/AI4BI_check/file_storage'
file_chunck_path='/Users/vinayakmoudgil/Documents/my_work/Projects_vinni/AI4BI_check/file_storage/file_chunk'
ALLOWED_EXTENSIONS = {'txt', 'csv', 'xlsx'}
charts_storage='/Users/vinayakmoudgil/Documents/my_work/Projects_vinni/AI4BI_check/static/charts_storage'
charts_archive_storage='/Users/vinayakmoudgil/Documents/my_work/Projects_vinni/AI4BI_check/static/charts_archive'
def get_json_ai(ai_response,start_ai,end_ai):
    try:
        json.loads(ai_response[start_ai:end_ai+1])
        return 0
    except Exception as e:
        print(f"Got the below error while converting to JSON :{e}")
        return -1
        
def get_charts_output(actual_resp,df):
  try:
    for i in actual_resp["metrics"]:
        if i["chart_type"].lower()=='line':
            if i["aggregation_type"].upper()=='SUM':
              line_df=df.groupby(i["x_axis"])[i["aggregation_column"]].sum().reset_index()
              fig=line_chart(df_data=line_df,x_axis=i["x_axis"],y_axis=i["y_axis"],kpi_name=i["name"])
              save_html_chart(fig, f'{i["name"].replace(" ","_")}.html')
            else:
              line_df=df.groupby(i["x_axis"])[i["aggregation_column"]].mean().reset_index()
              fig=line_chart(df_data=line_df,x_axis=i["x_axis"],y_axis=i["y_axis"],kpi_name=i["name"])
              save_html_chart(fig, f'{i["name"].replace(" ","_")}.html')
        if i["chart_type"].lower()=='bar':
            if i["aggregation_type"].upper()=='SUM':
              bar_df=df.groupby(i["x_axis"])[i["aggregation_column"]].sum().reset_index()
              fig=bar_chart(df_data=bar_df,x_axis=i["x_axis"],y_axis=i["y_axis"],kpi_name=i["name"])
              save_html_chart(fig, f'{i["name"].replace(" ","_")}.html')
            else:
              bar_df=df.groupby(i["x_axis"])[i["aggregation_column"]].mean().reset_index()
              fig=bar_chart(df_data=bar_df,x_axis=i["x_axis"],y_axis=i["y_axis"],kpi_name=i["name"])
              save_html_chart(fig, f'{i["name"].replace(" ","_")}.html')
    return 0
  except Exception as e:
     print(f"Got the below exception {str(e)}")
     return -1
def save_html_chart(chart, filename):
    # Save the HTML representation of the chart to a file
    with open(os.path.join(charts_storage, filename), 'w') as file:
        file.write(chart.to_html(full_html=False))  
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_all_keys(json_data):
    keys = set()

    if isinstance(json_data, dict):
        for key, value in json_data.items():
            keys.add(key)
            keys.update(get_all_keys(value))
    elif isinstance(json_data, list):
        for item in json_data:
            keys.update(get_all_keys(item))

    return keys
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = file_storage_folder

@app.route('/', methods=['GET', 'POST'])
@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            print(url_for('DfViewer',name=filename))
            return redirect(url_for('DfViewer',name=filename))
    return '''
    <!doctype html>
    <title>AI4BI</title>
    <h1>Upload a file to get Business.</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''

@app.route('/DfViewer/<name>')
def DfViewer(name):
    file_type=f'comma'
    default_encoding='utf-8'
    if name.endswith('xlsx'):
        file_type='Excel'
    elif name.endswith('csv'):
        try:
            with open(os.path.join(file_storage_folder,name), 'r') as file:
                lines = [file.readline() for _ in range(5)]
            # Check for comma (CSV) and pipe (PSV) separators
            if any(',' in line for line in lines):
                file_type= 'comma'
            elif any('|' in line for line in lines):
                file_type= 'pipe'                
        except:
                file_type= 'comma'
    try:
        chunk_file_name=str(name.split('.')[0])+'_chunk.'+str(name.split('.')[-1])
        with open(os.path.join(file_storage_folder,name), 'r') as input_file:
            first_5_lines = input_file.readlines()[:5]
        with open(os.path.join(file_chunck_path,chunk_file_name), 'w') as output_file:
            output_file.writelines(first_5_lines)
        if file_type=='pipe':
            df=pd.read_csv(os.path.join(file_chunck_path,chunk_file_name),sep='|',encoding=default_encoding)
        else:
            df=pd.read_csv(os.path.join(file_chunck_path,chunk_file_name),encoding=default_encoding)
    except UnicodeDecodeError as unerr:
        default_encoding='latin-1'
        df=pd.read_csv(os.path.join(file_storage_folder,name),encoding=default_encoding)
        
    return render_template('DataFrame.html', tables=[df.to_html()], name=name,file_type=file_type,default_encoding=default_encoding,titles=[''])

@app.route('/genBi/<name>', methods=['GET', 'POST'])
def gen_bi(name):
    try:
        df =pd.read_csv(os.path.join(file_storage_folder,name))
    except UnicodeDecodeError as unerr:
        df=pd.read_csv(os.path.join(file_storage_folder,name),encoding='latin-1') 
    column_list=[x for x in df.columns]
    ai_check=-1
    while ai_check<0:
        ai_response=generate_kpi(df_columns=column_list)
        start_ai=ai_response.find('{')
        end_ai=ai_response.rfind('}')
        ai_check=get_json_ai(ai_response=ai_response,start_ai=start_ai,end_ai=end_ai)
        print(f" The KPI response {ai_response}")
    json_response=json.loads(ai_response[start_ai:end_ai+1]) 
    json_keys_list=list(get_all_keys(json_response))
    for json_metadata in json_keys_list:
        if json_metadata.lower()=='kpis':
            json_header=json_metadata
        elif re.search('columns', json_metadata.lower()):
            json_column=json_metadata
        else:
            json_kpi_key=json_metadata   
    actual_display={}
    print(f" The Actual KPI shown {json_response}")
    for data in json_response[json_header]:
        if len(data[json_column])>1:
            actual_display[data[json_kpi_key]]=','.join(data[json_column])
    # remove all the charts from the directory and create new ones as per the AI
    try:
        output=-1
        while output<0:
            for filename in os.listdir(charts_storage):
                file_path = os.path.join(charts_storage, filename)
                archive_path=os.path.join(charts_archive_storage, filename)
                shutil.move(file_path, archive_path)
            ai_chart_response=generate_chart(kpi_data=actual_display)
            start_chart_ai=ai_chart_response.find('{')
            end_chart_ai=ai_chart_response.rfind('}')
            actual_chart_resp=json_response=json.loads(ai_chart_response[start_chart_ai:end_chart_ai+1])
            print(f" The Actual chart shown {actual_chart_resp}")
            output=get_charts_output(df=df,actual_resp=actual_chart_resp)
    except Exception as e:
        print(f"Got the below exception {str(e)}")

    files = os.listdir(charts_storage)
    html_files = []
    # Iterate through the files and add them to the list
    for file_name in files:
        file_path = os.path.join(charts_storage, file_name)
        if os.path.isfile(file_path):
            html_files.append('charts_storage/'+file_name)
    print(html_files)
    return render_template('AiOnBi.html', kpi_response=actual_display, name=name,html_files=html_files)