import datetime

WEEKDAY_MAP = {'пн':0, 'вт':1, 'ср':2, 'чт':3, 'пт':4, 'сб':5, 'нд':6}

# Повертає список дат для доставки

def generate_delivery_dates(start_date, days, delivery_count, periodicity):
    result = []
    i = 0
    created = 0
    while created < delivery_count:
        d = start_date + datetime.timedelta(days=i)
        if d.weekday() in days:
            if periodicity == '1/14' and created > 0:
                d = d + datetime.timedelta(days=7*(created))
            result.append(d)
            created += 1
        i += 1
    return result 