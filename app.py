from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response, send_file
import cv2 as cv
import numpy as np
import re, jwt, os, hashlib
from PIL import Image
import base64, io
from datetime import datetime,timedelta
from io import BytesIO
import shutil
import moviepy.editor as mp
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips
from moviepy.editor import ImageClip, concatenate_videoclips, ColorClip, transfx, CompositeVideoClip
import psycopg2, psycopg2.extras

def connect_to_database():
    conn_params = {
        'host': 'segfault-8969.8nk.gcp-asia-southeast1.cockroachlabs.cloud',
        'port': 26257,
        'user': 'ayush',
        'password': 'YSPHenhtCIY3PMWjEWhM0w',
        'database': 'imagesdatabase',
        'sslmode': 'verify-full',
        'sslrootcert': './root.crt' 
    }

    conn_str = "host={host} port={port} user={user} password={password} dbname={database} sslmode={sslmode} sslrootcert={sslrootcert}".format(**conn_params)
    
    try:
        conn = psycopg2.connect(conn_str)
        return conn
    except psycopg2.OperationalError as e:
        return None

conn = connect_to_database()
cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

app = Flask(__name__)

app.config['SECRET_KEY'] = 'ayushraghavasmit'

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def generate_token(username):
    expiration_time = datetime.utcnow() + timedelta(minutes=60)
    return jwt.encode({'username': username, 'exp': expiration_time}, app.config['SECRET_KEY'], algorithm='HS256')

def get_user_id_from_token(token):
    try:
        data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        return data.get('username')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None  
    
def convertToBLOBData(file):
    binaryData = file.read()
    return binaryData

def generate_video_from_images(directory, output_filename,image_duration, transition='fade', fps=24):
    if os.path.exists(output_filename):
        os.remove(output_filename)
    image_files = [f for f in os.listdir(directory) if f.endswith(('.png', '.jpg', '.jpeg'))]
    image_files.sort()  
    clips = []
    for index,image_file in enumerate(image_files):
        image_path = os.path.join(directory, image_file)
        image_clip = ImageClip(image_path, duration=image_duration[index])
        video_clip = image_clip.set_duration(image_duration[index])
        clips.append(video_clip)

    transition_clips = []
    for clip in clips:
        if transition == 'fade':
            transition_clip = clip.fadeout(1).fadein(1)
        elif transition == 'crossfadein':
            transition_clip = clip.crossfadein(1)
        elif transition == 'crossfadeout':
            transition_clip = clip.crossfadeout(1)
        elif transition == 'slidein':
            transition_clip = CompositeVideoClip([clip.fx(transfx.slide_out, duration=0.4, side="right")])
        elif transition == 'slideout':
            transition_clip = CompositeVideoClip([clip.fx(transfx.slide_out, duration=0.4, side="left")])
        elif transition == 'dull':
            color_clip = ColorClip((clip.w, clip.h), color=(150, 150, 150), ismask=True, duration=clip.duration)
            transition_clip = CompositeVideoClip([clip.set_duration(clip.duration).set_mask(color_clip)])
        elif transition == 'expand':
            resize_factor = 0.1  
            num_frames = 3       
            zoom_clips = [clip.resize(1 + resize_factor * j) for j in range(num_frames)]
            transition_clip = concatenate_videoclips(zoom_clips, method="compose")
        else:
            transition_clip = clip.fadeout(1).fadein(1)
        transition_clips.append(transition_clip)
    final_clip = concatenate_videoclips(transition_clips, method="compose")
    final_clip.write_videofile(output_filename, fps=fps, codec='mpeg4', audio_codec='aac', threads=4)


def generate_video_with_audio(video_path, audio_paths, output_path, audioDurations):
    video = mp.VideoFileClip(video_path)

    audio_clips = []
    for index,audio_path in enumerate(audio_paths):
        audio = mp.AudioFileClip(audio_path)
        trimmed_audio = audio.subclip(0, audioDurations[index])
        audio_clips.append(trimmed_audio)

    concatenated_audio = mp.concatenate_audioclips(audio_clips)
    concatenated_audio = concatenated_audio.set_duration(video.duration)

    video = video.set_audio(concatenated_audio)
    video.write_videofile(output_path)

@app.route('/')
@app.route('/index', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    # try:
    #     cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
    # except psycopg2.InterfaceError as e:
    #     if conn:
    #         if cursor:
    #             cursor.close()
    #         conn.close()
    #     conn = None
    #     cursor = None
    #     conn = connect_to_database()
    #     cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)    

    cursor.execute("SELECT user_name, user_email FROM user_details")
    users_data = cursor.fetchall()

    users = []
    for idx, user_data in enumerate(users_data, start=1):
        username = user_data['user_name']
        email = user_data['user_email']
        users.append({'Usernumber': idx, 'Username': username, 'Email': email})

    return render_template('admin.html', users=users)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and password == 'admin':
            return redirect(url_for('admin'))
        # try:
        #     cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        # except psycopg2.InterfaceError as e:
        #     if conn:
        #         if cursor:
        #             cursor.close()
        #         conn.close()
        #     conn = None
        #     cursor = None
        #     conn = connect_to_database()
        #     cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

        cursor.execute('SELECT * FROM user_details WHERE user_name = %s ', (username,))
        account = cursor.fetchone()
        if account:
            hashed_input_password = hash_password(password)
            if hashed_input_password == account['user_password']:
                token = generate_token(username)
                msg = 'Logged in successfully !'
                response = make_response(redirect(url_for('upload', msg=msg)))
                response.set_cookie('token', token, httponly=True) 
                return response
            else:
                msg = 'Incorrect password !'
                return render_template('loginpage.html', msg=msg)
        else:
            msg = 'Incorrect username!'
            return render_template('loginpage.html', msg=msg)
    else:
        if request.cookies.get('token') is not None:
            return redirect(url_for('upload'))
        return render_template('loginpage.html', msg='')


@app.route('/logout')
def logout():
    response = make_response(redirect(url_for('login')))
    response.set_cookie('token','',expires=0)
    return response

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    msg = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        if username.lower() == 'admin':
            msg = 'Username cannot be "admin"!'
            return render_template("signuppage.html", msg=msg)

        hashed_password = hash_password(password)
        # try:
        #     cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        # except psycopg2.InterfaceError as e:
        #     if conn:
        #         if cursor:
        #             cursor.close()
        #         conn.close()
        #     conn = None
        #     cursor = None
        #     conn = connect_to_database()
        #     cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

        cursor.execute('SELECT * FROM user_details WHERE user_name = %s OR user_email = %s', (username, email,))
        account = cursor.fetchone()
        if account:
                msg = 'Username or Email already exists!'
                return render_template("signuppage.html",msg=msg)
        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address !'
            return render_template("signuppage.html",msg=msg)
        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers !'
            return render_template("signuppage.html",msg=msg)
        else:
            cursor.execute('INSERT INTO user_details VALUES (%s, %s, %s)', (username, email, hashed_password))
            conn.commit()
            msg = 'You have successfully registered !'
            return redirect(url_for('login'))
    else:
        if request.cookies.get('token') is not None:
            return redirect(url_for('upload'))
        return render_template('signuppage.html', msg=msg)   

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    token = request.cookies.get('token')
    if not token: 
        return render_template('loginpage.html',msg="Login to use our services")
    user_id = get_user_id_from_token(token)
    if user_id is None:
        return render_template('loginpage.html', msg="Your session has expired or is invalid. Please log in again.")
    if not user_id:
        msg =  "This is an invalid user"
        return render_template('loginpage.html', msg=msg)

    if request.method == 'POST':
        uploaded_files = request.files.getlist('imgfiles')
        search_image_text = request.form.get("search_image", "")
        selected_image_text = request.form.getlist('imagesSelected')        

        if uploaded_files:
            try:
                # try:
                #     cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
                # except psycopg2.InterfaceError as e:
                #     if conn:
                #         if cursor:
                #             cursor.close()
                #         conn.close()
                #     conn = None
                #     cursor = None
                #     conn = connect_to_database()
                #     cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)

                for file in uploaded_files:
                    image_data = convertToBLOBData(file)
                    filename = file.filename
                    upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    extension = os.path.splitext(filename)[1]
                    cursor.execute('INSERT INTO images (Image_Name, User_Name, Image_Data, Extension, Upload_Time) VALUES (%s, %s, %s, %s, %s)',
                                   (filename, user_id, image_data, extension, upload_time))
                conn.commit()
                uploaded_files = None
                return jsonify({'message': 'Images uploaded successfully'}), 200
            except Exception as e:
                uploaded_files = None
                return jsonify({'error': str(e)}), 500
        elif search_image_text:
            try: 
                search_image_text = request.form['search_image']
                # try:
                #     cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
                # except psycopg2.InterfaceError as e:
                #     if conn:
                #         if cursor:
                #             cursor.close()
                #         conn.close()
                #     conn = None
                #     cursor = None
                #     conn = connect_to_database()
                #     cursor = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
                    
                cursor.execute( f"SELECT image_data,extension FROM images WHERE User_Name='{user_id}' and image_name LIKE '{search_image_text}%'",)
                images_received = cursor.fetchall()
                images_to_send = list()
                for x in images_received:
                    image_data_base64 = base64.b64encode(x['image_data']).decode('utf-8')
                    images_to_send.append({'image_data': image_data_base64, 'extension': x['extension']})
                    search_image_text = None
                return jsonify({'images': images_to_send}), 200 
            except Exception as e:
                search_image_text = None
                return jsonify({'error': str(e)}), 500  
            
        elif selected_image_text:
            try:
                images = []
                path = f'./static/users/{user_id}'
        
                if os.path.exists(f'{path}'):                
                    shutil.rmtree(path)
                os.makedirs(path)
        
                i = 0
                for key in selected_image_text:
                    x = base64.b64decode(key[23:])
                    with open(f"{path}/image{i}.png","wb") as fh:
                        fh.write(x)
                    i += 1
                    
                if os.path.exists(f'{path}/video.mp4'):
                    os.remove(f'{path}/video.mp4')
                image_folder = path                    
        
                video_path = f'{path}/video.mp4'
                fps = 24
                transition = request.form.get('transition', 'fade')
                quality = request.form.get('quality', '1920x1080')
                duration = request.form.getlist('duration')
                width, height = map(int, quality.split('x'))
        
                generate_video_from_images(path, video_path, transition=transition, image_duration=duration, fps=fps)
        
                audio_paths = [f"static/audio/{audio_path}.mp3" for audio_path in request.form.getlist('audio')]
                final_video_path = f"{path}/finalvideo.mp4"
                generate_video_with_audio(video_path, audio_paths, final_video_path, request.form.getlist('audioduration'))
        
                return jsonify({'message': 'Video generated successfully'}), 200
            except Exception as e:
                return jsonify({'error': str(e)}), 500           
    return render_template('uploadpage.html', user=user_id)   

if __name__ == "__main__":
    app.run(debug=True)

    