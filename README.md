# radarr_netimport
A sloppy python code to fetch movies from TMDB list and add them to radarr.
Radarr has this feature built-in but radarr uses TMDB API v3 and I have noticed that if using v3 API, TMDB only returns 
maximum of 500 movies in the list. This is resolved if using TMDB API v4. 

# Config
Script variables are passed as environment variables. Supported variables are;

* TMDB_ACCESS_TOKEN: TMDB access token, this will be under you account settings on TMDB
* TMDB_API_KEY: TMDB API key. You will be able to get this with your account
* TMDB_LIST_ID: ID of the list on TMDB
* RADARR_IP: IP address where radarr is listening
* RADARR_PORT: Port number for radarr. default is 7878
* RADARR_API_KEY: API key for radarr
* SYNC_INTERVAL: Interval at which to sync movies from TMDB with radarr in seconds
* QUALITY_PROFILE_ID: Radarr quality profile. Profile `any` has ID of 1. _type: integer_
* ROOT_FOLDER_PATH: root folder where movie will be stored.

# Docker Image
Docker image is available at: https://hub.docker.com/r/thundermagic/radarr_netimport.  
Docker image is multi arch. Supported architectures are `arm`, `arm64` and `amd64`.  
Docker manifest is used for multi arch awareness. So you just need to pull the image regardless of the underlying 
platform and the correct image will be pulled.  

#### Example docker compose
```yaml
version: "3"
services:
    radarr_netimport:
        image: thundermagic/radarr_netimport:latest
        restart: on-failure
        container_name: radarr_netimport
        environment:
          - TMDB_ACCESS_TOKEN=sampletoken
          - TMDB_API_KEY=tvdb_api_key
          - TMDB_LIST_ID=12345
          # IP address and port number where radarr can be accessed
          - RADARR_IP=192.168.4.4
          - RADARR_PORT=7878
          # radarr API key. This is on radarr under settings>general
          - RADARR_API_KEY=radarr_api_key
          - SYNC_INTERVAL=3600  # Interval at which to sync with TMDB, in seconds
          - QUALITY_PROFILE_ID=1  # 1 is profile any
          - ROOT_FOLDER_PATH=/movies/  # Full path of root folder
```
