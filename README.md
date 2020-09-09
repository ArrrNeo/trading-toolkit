This project started as a way to give me better interface for robinhood I had few features in my mind like:
1) options vs shares vs cash allocation.
2) include gold/silver and derative ETFs in cash
3) give me pie chart of allocation for various tickers in my portfolio.
4) historical data of daily/weekly/monthly profit loss
5) and many more.

For my own trading, I am interested in filtering out data in a way which I could not find online. So I started developing tool to help me in that.
This project is collection of those tools (and possible more to come)
1) Debit spread chart.
   This plots for a given stock and date "debit spread" vs "max profit percentage"
2) Covered Call screener.
   This plots for given filters "covered calls" vs "max profit percentage"

![Image Debit Spread Chart](./media/debit_spread.png)

Anyways here is rest of the readme. This project was cloned from https://github.com/app-generator/django-dashboard-corona-dark but then I changed the remote url to point to my empty repo, that is why I now have lost fork connection. The reason I did this was because initially I was not careful about checking in robinhood credentials and accidently uploaded to github once and twice. I need to make the repo private which was not allowed for a forked repo. Since then I have fixed robinhood credential reading mechanism so that I dont accidently check it in.

## How to use it

```bash
$ # Get the code
$ git clone https://github.com/ArrrNeo/django-dashboard-corona-dark.git
$ cd django-dashboard-corona-dark
$
$ # Virtualenv modules installation (Unix based systems)
$ virtualenv env
$ source env/bin/activate
$
$ # Virtualenv modules installation (Windows based systems)
$ # virtualenv env
$ # .\env\Scripts\activate
$
$ # Install modules - SQLite Storage
$ pip3 install -r requirements.txt
$
$ # Create tables
$ python manage.py makemigrations
$ python manage.py migrate
$
$ # Start the application (development mode)
$ python manage.py runserver # default port 8000
$
$ # Start the app - custom port
$ # python manage.py runserver 0.0.0.0:<your_port>
$
$ # Access the web app in browser: http://127.0.0.1:8000/
```

## For Heroku deployment
```bash
$ # make sure following configs are set
$ heroku config:set HEROKU_DEPLOYEMENT=1
$
$ heroku config:set CELERY_BROKER_URL="your CELERY_BROKER_URL addon url"
$
$ heroku config:set CELERY_RESULT_BACKEND="your CELERY_RESULT_BACKEND addon url"
```

## Credits & Links

- [Django](https://www.djangoproject.com/) - The offcial website
- [Original repo](https://github.com/app-generator/django-dashboard-corona-dark) - App Generator

<br />
