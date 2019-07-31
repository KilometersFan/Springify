from flask import Flask, request, redirect, render_template, url_for, session
import spotipy
from spotipy import oauth2
import pprint
import operator
import os

app = Flask(__name__)
app.secret_key = ""

CLIENT_ID = ''
CLIENT_SECRET = ''
REDIRECT_URI = "http://localhost:5000/home"
SCOPE = "playlist-modify-private playlist-read-private playlist-modify-public user-follow-read user-library-modify user-library-read"
CACHE = ".spotipyoauthcache"
sp = None
current_user = None
sp_oauth = oauth2.SpotifyOAuth(CLIENT_ID,CLIENT_SECRET,REDIRECT_URI,scope=SCOPE,cache_path=CACHE)
@app.route("/", methods=['GET'])
def render_welcome():
    return render_template('welcome.html')

@app.route('/signout', methods=['GET'])
def signout():
    os.remove('.spotipyoauthcache')
    return render_template('welcome.html', msg="Successfully signed out.")

#Below is authorization logic when a user first visits the app
@app.route("/home", methods=['GET'])
def authorize():
    global sp
    global current_user
    access_token = ""
    token_info = sp_oauth.get_cached_token()
    if token_info:
        print("Found cached token!")
        access_token = token_info['access_token']
    else:
        url = request.url
        print(url)
        code = sp_oauth.parse_response_code(url)
        if code:
            print("Found Spotify auth code in Request URL! Trying to get valid access token...")
            token_info = sp_oauth.get_access_token(code)
            access_token = token_info['access_token']
    if access_token:
        sp = spotipy.Spotify(access_token)
        current_user = sp.current_user()
        return render_template('home.html', user=current_user)
    else:
        return redirect(sp_oauth.get_authorize_url(show_dialog=True))

#Below is the logic for deleting playlist(s)
@app.route('/playlists', methods=['GET'])
def render_delete_playlists():
    if validate():
        total_playlists = return_playlists()
        return render_template('delete_playlists.html', error="", total_playlists=total_playlists, user=current_user)
    else:
        return render_template('error.html',error='Unable to get access token.')

@app.route('/playlists/delete', methods=["GET"])
def delete_playlists():
    if validate():
        action = request.args.get('submit')
        if(action == "delete"):
            print('Attempting to delete playlists')
            try:
                if(len(request.args) < 2):
                    print('No playlist selected')
                    total_playlists = return_playlists()
                    return render_template('delete_playlists.html', error="Please choose at least one playlist to delete.", total_playlists=total_playlists, user=current_user)
                else:
                    print('Playlist(s) chosen')
                    ids = request.args.getlist('playlist')
                    for id in ids:
                        print("Deleting " + id + " from " + current_user['id'])
                        sp.user_playlist_unfollow(current_user['id'], id)
                    total_playlists = return_playlists()
                    return render_template('delete_playlists.html', msg='Successfully deleted playlist(s)', total_playlists=total_playlists, user=current_user)
            except:
                return render_template('error.html', error="Unable to delete playlist(s)")   
    else:
        return render_template('error.html',error='Unable to get access token.')

#Below is the logic for unfollowing artists/users
@app.route('/accounts', methods=['GET'])
def render_unfollow_users():
    if validate():
        total_users = return_followed()
        return render_template('unfollow.html', following=total_users, user=current_user)
    else:
        return render_template('error.html',error='Unable to get access token.')

@app.route('/accounts/unfollow', methods=['GET'])
def unfollow_users():
    if validate():
        action = request.args.get('submit')
        if(action == "unfollow"):
            print('Attempting to unfollow users')
            try:
                if(len(request.args) < 2):
                    print('No user selected')
                    total_users = return_followed()
                    return render_template('unfollow.html', error="Please choose at least one artist/user to unfollow.", following=total_users, user=current_user)
                else:
                    ids = request.args.getlist('account')
                    idString = ','.join(ids)
                    sp._delete("me/following?type=artist&ids=" + idString)
                    total_users = return_followed()
                    return render_template('unfollow.html', msg='Successfully unfollowed account(s)', following=total_users, user=current_user)
            except:
                return render_template('error.html', error="Unable to delete user(s)/artist(s)")   
    else:
        return render_template('error.html', error="Unable to obtain access token")

#Below is the logic for deleting tracks off of a particular playlist or all playlists
@app.route('/tracks', methods=['GET'])
def render_remove():
    if validate():
        total_playlists = return_playlists()
        return render_template('playlists.html', total_playlists=total_playlists, user=current_user)
    else:
        return render_template('error.html',error='Unable to get access token.')

@app.route('/tracks/remove', methods=['GET'])
def render_remove_playlist():
    if validate():
        playlist_info = str.split(request.args.get('playlist_info'),',')
        id = playlist_info[0]
        name= playlist_info[1]
        total_items = return_tracks(id)
        return render_template('remove.html',name=name, items=total_items, id=id, user=current_user)
    else:
        return render_template('error.html',error='Unable to get access token.')

@app.route('/tracks/remove/<playlist_id>/<name>', methods=['GET'])
def delete_tracks(playlist_id, name):
    print("Current playlist: " + playlist_id)
    action = request.args.get('submit')
    if validate():
        if(action == "delete"):
            print('Attempting to delete tracks')
            try:
                ids = request.args.getlist('track')
                print(ids)
                if(len(ids) == 0):
                    total_items = return_tracks(playlist_id)
                    return render_template('remove.html', name=name, items=total_items, id=playlist_id, user=current_user, error="Please choose at least one track to delete.")
                else:
                    if(request.args.get('unsave') == 'true'):
                        print("Trying to remove from saved")
                        sp.current_user_saved_tracks_delete(ids)
                    if(request.args.get('allInstances') == 'true'):
                        print('Attempting to remove from all playlists')
                        playlist_ids = return_playlists(True)
                        for id in playlist_ids:
                            sp.user_playlist_remove_all_occurrences_of_tracks(current_user['id'], id, ids)
                        print('Successfully removed from all playlists!')
                        total_items = return_tracks(playlist_id)
                        return render_template('remove.html', name=name, items=total_items, id=playlist_id, user=current_user, msg='Successfully removed track(s)')
                    else:
                        sp.user_playlist_remove_all_occurrences_of_tracks(current_user['id'], playlist_id, ids)
                        print('Successfully removed from this playlist: ',playlist_id)
                        total_items = return_tracks(playlist_id)
                        return render_template('remove.html', name=name, items=total_items, id=playlist_id, user=current_user, msg='Successfully removed track(s)')
            except:
                return render_template('error.html', error="Unable to delete track(s)")
    else:
        return render_template('error.html', error="Unable to obtain access token")
    return 'Ok'

#Below is the logic for springify
@app.route('/springify', methods=["GET"])
def render_springify():
    if validate():
        total_playlists = return_playlists()
        return render_template('springify.html', total_playlists=total_playlists, user=current_user)
    else:
        return render_template('error.html',error='Unable to get access token.')

@app.route('/springify/tracks', methods=["GET"])
def render_select_tracks():
    if validate():
        playlist_info = str.split(request.args.get('playlist_info'),',')
        id = playlist_info[0]
        name= playlist_info[1]
        print(id, name)
        total_items = return_tracks(id)
        return render_template('select_tracks.html', name=name, items=total_items, id=id, user=current_user)
    else:
        return render_template('error.html',error='Unable to get access token.')

@app.route('/springify/tracks/<playlist_id>/<name>/results', methods=["GET"])
def process_tracks(playlist_id, name):
    print(playlist_id, name)
    if validate():
        features = ["acousticness", "danceability", "energy", "instrumentalness", "liveness", "loudness", "speechiness", "tempo", "valence"]
        multipliers = [100, 100, 100, 100, 100, 10/6, 100, .5, 100]
        form_features = request.args.getlist('feature')
        requestArgs = list(request.args.copy().items())
        for feature in features:
            if(feature in form_features):
                requestArgs.remove(feature)
        if(len(requestArgs) == 0):
            total_items=return_tracks(playlist_id)
            return render_template('select_tracks.html',name=name, items=total_items, id=playlist_id, user=current_user, error="Please select at least one track.")
        else:
            for i in range(len(features)):
                if(request.args.get(features[i]) == "True"):
                    multipliers[i] = 0
            selected_tracks = request.args.getlist('track')
            audio_features_selected = sp.audio_features(selected_tracks)
            otherTracks = return_tracks(playlist_id, True, selected_tracks)
            dictionary = {}
            for track_id,name in otherTracks:
                diff = 0
                track_audio = sp.audio_features(track_id)
                for audio_feature in audio_features_selected:
                    diff += multipliers[0] *abs(float(audio_feature['acousticness']) - float(track_audio[0]['acousticness']))
                    diff += multipliers[1] *abs(float(audio_feature['danceability']) - float(track_audio[0]['danceability']))
                    diff += multipliers[2] *abs(float(audio_feature['energy']) - float(track_audio[0]['energy']))
                    diff += multipliers[3] *abs(float(audio_feature['instrumentalness']) - float(track_audio[0]['instrumentalness']))
                    diff += multipliers[4] *abs(float(audio_feature['liveness']) - float(track_audio[0]['liveness']))
                    diff += multipliers[5] *abs(float(audio_feature['loudness']) - float(track_audio[0]['loudness']))
                    diff += multipliers[6] *abs(float(audio_feature['speechiness']) - float(track_audio[0]['speechiness']))
                    diff += multipliers[7] *abs(float(audio_feature['tempo']) - float(track_audio[0]['tempo']))
                    diff += multipliers[8] *abs(float(audio_feature['valence']) - float(track_audio[0]['valence']))
                dictionary[(track_id,name)] = round(diff,2) 
            sorted_dict = sorted(dictionary.items(), key=operator.itemgetter(1), reverse=True)
            session['springify_results'] = sorted_dict
            return render_template('results.html', playlist_id=playlist_id, name=name, tracks=sorted_dict, user=current_user)
    else:
        return render_template('error.html',error='Unable to get access token.')

@app.route('/springify/tracks/<playlist_id>/<name>/remove', methods=["GET"])
def springify_remove(playlist_id, name):
    print(playlist_id, name)
    action = request.args.get('submit')
    if validate():
        if(action == 'back'):
            print("redirecting back to springify")
            return redirect(url_for('render_springify'))
        elif(action == "delete"):
            print('Attempting to delete tracks')
            try:
                ids = request.args.getlist('track')
                sorted_dict = session['springify_results']
                if(len(ids) == 0):
                    return render_template('results.html', playlist_id=playlist_id, name=name, tracks=sorted_dict, user=current_user, error="Please choose at least one track to delete.")
                else:
                    new_sorted_dict = [item for item in sorted_dict if item[0][0] not in ids]
                    sp.user_playlist_remove_all_occurrences_of_tracks(current_user['id'], playlist_id, ids)
                    print('Successfully removed from this playlist: ', playlist_id)
                    return render_template('results.html', playlist_id=playlist_id, name=name, tracks=new_sorted_dict, user=current_user, msg='Successfully removed track(s)')
            except:
                return render_template('error.html', error="Unable to delete track(s)")
    else:
        return render_template('error.html', error="Unable to obtain access token")
    return 'Ok'

#Below is the logic for removing albums
@app.route('/album')
def render_albums():
    if validate():
        print('got token!')
        total_albums = return_albums()
        return render_template('album.html', total_albums=total_albums, user=current_user)
    else:
        return render_template('error.html',error='Unable to get access token.')

@app.route('/album/remove')
def remove_albums():
    if validate():
        print("Attempting to remove albums")
        try:
            if(len(request.args) < 2):
                print('No album selected')
                total_albums = return_albums()
                return render_template('album.html', error="Please choose at least one album.", total_albums=total_albums, user=current_user)
            else:
                print('Album(s) chosen')
                ids = request.args.getlist('album')
                sp._delete('me/albums/?ids=' + ','.join(ids))
                total_albums = return_albums()
                return render_template('album.html', msg="Successfully removed album(s).", total_albums=total_albums, user=current_user)
        except:
            return render_template('error.html', error="Unable to remove album(s)") 
    else:
        return render_template('error.html', error="Unable to attain access token.")

#Helper functions
def return_followed():
    total_users = []
    lastArtist = None
    artists = sp.current_user_followed_artists(limit=50, after=lastArtist)
    while(len(artists['artists']['items']) != 0):
        for item in artists['artists']['items']:
            total_users.append(item)
            lastArtist = item['id']
        artists = sp.current_user_followed_artists(limit = 50, after=lastArtist)
    return total_users

def return_playlists(idsOnly = False):
    global sp
    total_playlists = []
    count = 1
    playlists = sp.current_user_playlists(limit = 50)
    while(len(playlists['items']) != 0):
        for item in playlists['items']:
            if(idsOnly):
                if(sp.user_playlist(current_user['id'],item['id'])['owner']['id'] == current_user['id'] or sp.user_playlist(current_user['id'],item['id'])['collaborative'] == True):
                    total_playlists.append(item['id'])
            else:
                playlist_image = ""
                if(len(item['images']) > 0):
                    playlist_image = item['images'][0]['url']
                playlist_tuple=(item,playlist_image)
                total_playlists.append(playlist_tuple)
        playlists = sp.current_user_playlists(limit = 50, offset = 50 * count)
        count += 1
    return total_playlists

def return_tracks(playlist_id, springify=False, springifyList = None):
    global sp
    total_items = []
    results = sp.user_playlist(sp.current_user()['id'], playlist_id, 'tracks,next')
    tracks = results['tracks']
    for item in tracks['items']:
        if(springify and item['track']['id'] not in springifyList and item['track']['is_local'] == False):
            id_name = (item['track']['id'], item['track']['name'])
            total_items.append(id_name)
        elif(not springify):
            total_items.append(item)
    while(tracks['next']):
        tracks = sp.next(tracks)
        for item in tracks['items']:
            if(springify and item['track']['id'] not in springifyList and item['track']['is_local'] == False):
                id_name = (item['track']['id'], item['track']['name'])
                total_items.append(id_name)
            elif(not springify):
                total_items.append(item)
    return total_items

def return_albums():
    global sp
    total_albums = []
    count = 1
    albums = sp.current_user_saved_albums(limit = 50)
    while(len(albums['items']) != 0):
        for item in albums['items']:
            album_image = ""
            if(len(item['album']['images']) > 0):
                album_image = item['album']['images'][0]['url']
            album_tuple=(item,album_image)
            total_albums.append(album_tuple)
        albums = sp.current_user_saved_albums(limit = 50, offset = 50 * count)
        count += 1
    return total_albums

def validate():
    token_info = sp_oauth.get_cached_token()
    if token_info:
        global sp
        global current_user
        print("Found cached token!")
        access_token = token_info['access_token']
        sp = spotipy.Spotify(access_token)
        current_user = sp.current_user()
        return True
    return False

if __name__ == "__main__":
    app.run("localhost", 5000, True)