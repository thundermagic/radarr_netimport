from requests import get, post
import os
from time import sleep
from ratelimit import limits, sleep_and_retry
from concurrent.futures import ThreadPoolExecutor
from slugify import slugify


def _tmdb_list_by_page(page) -> list:
    """ TMDB API v4 uses pagination for lists. Each page return 20 movies. This function gets movies per page """

    resp = get(tmdb_url, headers=tmdb_headers, params={'page': page})
    if resp.ok:
        return resp.json()['results']
    else:
        return []


def tmdb_movies() -> list:
    """ Gets movies from tmdb list. Returns list of tmdb IDs of the movies """

    all_movies = []
    resp = get(tmdb_url, headers=tmdb_headers)
    if resp.ok:
        tmdb_list = resp.json()
        total_pages = tmdb_list['total_pages']
        movies: list = tmdb_list['results']
        all_movies.extend(movies)
        if total_pages > 1:
            with ThreadPoolExecutor() as executor:
                output = executor.map(_tmdb_list_by_page, list(range(2, total_pages + 1)))
                for res in output:
                    all_movies.extend(res)

        # We are interested in just getting the tmdb IDs
        return [movie['id'] for movie in all_movies]
    else:
        raise ValueError('Unable to retrieve movies from tmdb. HTTP response code: {0}, HTTP response content: {1}'.format(
            resp.status_code, resp.content
        ))


def radarr_movies() -> list:
    """ Gets all movies from radarr and returns a list of tmdb IDs of the movies """

    resp = get(radarr_movie_url, params=radarr_api_params).json()
    return [res['tmdbId'] for res in resp]

# Ratelimiting to not overwhelm the radarr server
@sleep_and_retry
@limits(calls=10, period=60)
def add_radarr_movies(movie_details: dict) -> None:
    """ Adds movie to radarr. Input should be dict with keys: tmdbid, title and year (release year) """

    data = {
        'tmdbId': movie_details['tmdbid'],
        'qualityProfileId': radarr_quality_profile,
        'monitored': True,
        'rootFolderPath': radarr_root_folder,
        'title': movie_details['title'],
        'titleSlug': slugify(movie_details['title'] + ' {0}'.format(movie_details['tmdbid'])),
        'images': [],
        'year': movie_details['year'],
        'addOptions': {'searchForMovie': True}
    }

    print('Adding movie: {0} to radarr'.format(data))
    radarr_add = post(radarr_movie_url, json=data, params=radarr_api_params)
    if not radarr_add.ok:
        print('Could not add movie {0} to add. HTTP response: {1}'.format(movie_details['title'], radarr_add.content))
    return None


# TMDB api has quite a low api call limit. Though the TMDB api documentation says that the limit is 40 calls per 10 seconds
# but limiting the calls to this wasn't working. After some experimenting 5 calls per 15 seconds seems to work fine.
@sleep_and_retry
@limits(calls=5, period=15)
def get_movie_info(tmdb_id: int) -> list:
    """ Returns movie title and release date (year) for only the movies that are released """

    headers = {
        'Content-Type': 'application/json'
    }
    params = {
        'api_key': tmdb_api_key,
    }
    url = 'https://api.themoviedb.org/3/movie/{0}'.format(tmdb_id)
    print('Getting movie info for movie: {0}'.format(tmdb_id))
    resp = get(url, headers=headers, params=params)
    result = []
    if resp.ok:
        details = resp.json()
        if not details['release_date']:
            print('Skipping this movie because probably its not released yet. Movie details: {0}'.format(details))
            return result
        result.append({'title': details['original_title'],
                       'year': details['release_date'].split('-')[0],
                       'tmdbid': details['id']})
        return result
    else:
        print('Unable to get movie info for TMDB ID: {0}. HTTP status code: {1}, HTTP response: {2}'.format(tmdb_id,
                                                                                                       resp.status_code,
                                                                                                       resp.content))
        return result


if __name__ == '__main__':

    sync_interval = os.environ.get('SYNC_INTERVAL')
    if sync_interval is None:
        raise ValueError('Sync interval cannot be empty')

    tmdb_access_token = os.environ.get('TMDB_ACCESS_TOKEN')
    tmdb_api_key = os.environ.get('TMDB_API_KEY')
    tmdb_list_id = os.environ.get('TMDB_LIST_ID')

    radarr_ip = os.environ.get('RADARR_IP')
    radarr_port = os.environ.get('RADARR_PORT')
    radarr_api_key = os.environ.get('RADARR_API_KEY')
    radarr_root_folder = os.environ.get('ROOT_FOLDER_PATH')
    radarr_quality_profile = os.environ.get('QUALITY_PROFILE_ID')

    if tmdb_access_token is None\
            or tmdb_api_key is None\
            or tmdb_list_id is None\
            or radarr_ip is None\
            or radarr_port is None\
            or radarr_api_key is None \
            or radarr_root_folder is None \
            or radarr_quality_profile is None:
        raise ValueError('Config variables cannot be empty')

    tmdb_url = 'https://api.themoviedb.org/4/list/{0}'.format(tmdb_list_id)
    tmdb_headers = {
        'Authorization': 'Bearer {0}'.format(tmdb_access_token)
    }

    radarr_movie_url = 'http://{0}:{1}/api/movie'.format(radarr_ip, radarr_port)
    radarr_api_params = {'apikey': '{0}'.format(radarr_api_key)}

    while True:
        print('Sleeping for {0} seconds'.format(sync_interval))
        print()
        sleep(int(sync_interval))

        print('Getting movies from TMDB list')
        movies_from_tmdb = tmdb_movies()
        print('Retrieved {0} movies from TMDB list'.format(len(movies_from_tmdb)))

        print('Getting movies from radarr')
        movies_from_radarr = radarr_movies()
        print('Retrieved {0} movies from radarr'.format(len(radarr_movies())))

        movies_to_add = set(movies_from_tmdb).difference(set(movies_from_radarr))
        if movies_to_add:
            print('{0} movies to add with TMDB IDs of: {1}'.format(len(movies_to_add), movies_to_add))
            # Need to get movie details from TMDB, especially the correct release date. This is needed before movie
            # can be added to radarr. I have noticed that for some movies the release date returned in the first call
            # to TMDB (tmdb_movies) is incorrect. This then causes issue when adding the movie to radarr. To avoid this
            # another call is made to TMDB to specifically fetch the movie details.
            movies_info = []
            with ThreadPoolExecutor() as executor:
                output = executor.map(get_movie_info, movies_to_add)
                for out in output:
                    movies_info.extend(out)

            print('{0} movie(s) eligible to be added to radarr'.format(len(movies_info)))
            with ThreadPoolExecutor() as executor:
                _ = executor.map(add_radarr_movies, movies_info)
        else:
            print('No movies to add to radarr')

