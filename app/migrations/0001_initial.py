# Generated by Django 2.2.10 on 2020-07-14 06:36

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='robinhood_crypto',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('code', models.CharField(max_length=5)),
                ('quantity', models.FloatField()),
                ('average_price', models.FloatField()),
                ('open_price', models.FloatField()),
                ('current_price', models.FloatField()),
                ('equity', models.FloatField()),
                ('cost_basis', models.FloatField()),
                ('unrealized_p_l', models.FloatField()),
                ('unrealized_p_l_percent', models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name='robinhood_options',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('chain_symbol', models.CharField(max_length=5)),
                ('option_id', models.CharField(max_length=52)),
                ('expiration_date', models.CharField(max_length=20)),
                ('option_type', models.CharField(max_length=5)),
                ('strike_price', models.FloatField()),
                ('average_price', models.FloatField()),
                ('quantity', models.FloatField()),
                ('previous_close_price', models.FloatField()),
                ('current_price', models.FloatField()),
                ('equity', models.FloatField()),
                ('cost_basis', models.FloatField()),
                ('unrealized_p_l', models.FloatField()),
                ('unrealized_p_l_percent', models.FloatField()),
                ('today_p_l', models.FloatField()),
                ('today_p_l_percent', models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name='robinhood_stocks',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('symbol', models.CharField(max_length=5)),
                ('name', models.CharField(max_length=30)),
                ('instrument_url', models.CharField(max_length=92)),
                ('average_price', models.FloatField()),
                ('quantity', models.FloatField()),
                ('open_price', models.FloatField()),
                ('latest_price', models.FloatField()),
                ('equity', models.FloatField()),
                ('cost_basis', models.FloatField()),
                ('unrealized_p_l', models.FloatField()),
                ('unrealized_p_l_percent', models.FloatField()),
                ('today_p_l', models.FloatField()),
                ('today_p_l_percent', models.FloatField()),
            ],
        ),
        migrations.CreateModel(
            name='robinhood_summary',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('options_equity', models.FloatField(default=0)),
                ('stocks_equity', models.FloatField(default=0)),
                ('crypto_equity', models.FloatField(default=0)),
                ('portfolio_cash', models.FloatField(default=0)),
                ('buying_power', models.FloatField(default=0)),
            ],
        ),
    ]
