# webm-project
(Hopefully) useful services related to viewing and creating WEBM files.
Currently the only project is "Screamer detector".

##Screamer detector
Django-based webservice, which helps 2ch.hk users properly adjust volume while watching WEBM videos and thus avoid hearing unpleasantly loud sounds.
###API
Screamer detector provides API with two methods suitable for Ajax calls:

1\. GET `/api/detect_screamers?url=https://2ch.hk/<...>.webm`

This method is used to synchronously check given URL.

Status code 200 indicated that no error happened during processing. In this case response body is valid JSON of form
`{'max_volume': <float>, 'screamer_chance': <0..100>, 'duration_msec': <integer>, 'volume_range': <float>}`

2\. POST `/api/detect_screamers_batch urls:["https://2ch.hk/<...>.webm"<,"https://2ch.hk/<...>.webm", <...>>]`

Response body contains JSON of form
`{"https://2ch.hk/<...>.webm": "<float|null>"<, "https://2ch.hk/<...>.webm": "<float|null>", <...>>}`

Which is maps subset of list of URLs from request to their maximum volume level. Or null, which means that WEBM volume can't be determined (due to network problems or WEBM having no audio).

This method doesn't block until all specified URLs are processed. It merely returns data from cache. That's why some of the URLs in request are absent in response - these aren't procesed yet. So it's good idea to wait some time and retry with request.
###Requirements
python >= 3.5.1 You might want to install virtualenv to use python3 along with python version 2 conveniently.

requests >= 2.9 (pip install requests)

django >= 1.9 (pip install django)

django-cors-headers >= 1.1.0 (pip install django-cors-headers)
###Usage
    python manage.py makemigrations
    python manage.py makemigrations corsheaders
    python manage.py migrate
    python manage.py createsuperuser --- optionally
    python manage.py runserver

By default server uses port 8000, so api methods are available at http://127.0.0.1:8000/api/detect_screamers<...>
