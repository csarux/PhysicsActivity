import pandas as pd
import matplotlib.pyplot as plt

acdf = pd.read_excel('PhysicistAvailabilities.xlsx')

phacdf = pd.read_excel('Z:/Radiofisica/RepartoDosimetrias.xls', usecols=[0, 19], nrows=8)
phacdf.columns = ['Physicist', 'Plans']

physicists = phacdf.Physicist.to_list()

phdict = {
    'Alfonso' : 'AL', 
    'César' : 'CR',
    'Guadalupe' : 'GM',
    'Carmen' : 'CC',
    'Pilar' : 'PJ',
    'Felipe' : 'FO',
    'Juan' : 'JC',
    'Juanma' : 'JP',
}


ppadf = pd.read_excel('Z:/Radiofisica/RepartoDosimetrias.xls', usecols=range(0,18), skiprows=11, dtype={'Fecha': 'datetime64[ns]'})
ppadf.Fecha = ppadf.Fecha.ffill()

locations = ppadf.columns[1:].to_list()

# Calculate business days difference between two dates
def business_days_between(start_date, end_date):
    """
    Returns the number of business days between start_date (inclusive) and end_date (exclusive).
    """
    if end_date <= start_date:
        return 0
    return pd.bdate_range(start_date, end_date - pd.Timedelta(days=1)).size

def create_physicist_activities(ppadf, physicists, location=None, complexity=False):
    complexities = {
        'ORL' : 1,
        'Pulmon' : 1,
        'Prostata3N' : 1,
        'Prostata2N y 1N' : 0.6,
        'Mama' : 0.8,
        'Sarcoma' : 1,
        'Recto' : 1,
        'Digestivo' : 1,
        'Linfoma' : 1,
        'Cerebral' : 1,
        'Electrones' : 0.5,
        'Piel' : 0.5,
        'SBRT/SRS': 1.4,
        'Ginecolog' : 1,
        'Benigna' : 0.5,
        'Otros' : 1,
        'Paliativo' : 0.5,
    }
   
    dates = ppadf.Fecha.unique()
    physicist_counts_by_date, physicist_counts, temp_physicist_counts = {}, {}, {}
    for date in dates:
        ppadf_date = ppadf[ppadf['Fecha'] <= date]
        for physicist in physicists:
            ppadf_date_df = pd.DataFrame((ppadf_date.iloc[:, 1:] == physicist).sum())
            ppadf_date_df.columns = ['plans']
            ppadf_date_df['weightedPlans'] = ppadf_date_df['plans'] * ppadf_date_df.index.map(complexities)
            if location is None:
                temp_physicist_counts[physicist] = ppadf_date_df['weightedPlans'].sum() if complexity else ppadf_date_df['plans'].sum()
                physicist_counts.update(temp_physicist_counts)
            else:
                temp_physicist_counts[physicist] = ppadf_date_df.loc[location]['weightedPlans'] if complexity else ppadf_date_df.loc[location]['plans']
                physicist_counts.update(temp_physicist_counts)
        physicist_counts_by_date.update({date: physicist_counts.copy()})
       
    acppadf = pd.DataFrame(physicist_counts_by_date)
    acppadf = acppadf.transpose()

    add_physicist_acum_availability(acppadf, acdf, physicists, phdict)
    
    add_physicist_norm_activity(acppadf, physicists, phdict)
    
    return acppadf

def physicist_acum_availability(acdf, physicist_ID, date):
    """
    Devuelve el ac_av acumulado para el physicist_ID indicado hasta la fecha dada (inclusive).
    """
    df = acdf.loc[(acdf.physicist == physicist_ID) & (acdf.date <= date)][['date', 'availability']].copy(deep=True)
    df = pd.concat([df, pd.DataFrame({'date': [date], 'availability': [False]})], ignore_index=False)
    df = df.sort_values('date').reset_index(drop=True)
    df['end_date'] = df['date'].shift(-1)
    df = df[df['end_date'].notna()]
    df['business_days'] = df.apply(lambda row: business_days_between(row['date'], row['end_date']), axis=1)
    df['ac_av'] = (df['availability'] * df['business_days']).cumsum()
    return df['ac_av'].max()

def add_physicist_acum_availability(acppadf, ac_df, physicists, phdict):
    """
    Añade columnas 'ac_<Physicist>' al dataframe acppa_df con la actividad acumulada
    para cada físico hasta la fecha de cada fila.
    
    Parámetros:
    - acppa_df: dataframe con fechas (índice DatetimeIndex) donde añadir columnas
    - ac_df: dataframe con physicist, date, availability, ac_av
    - physicists_list: lista de nombres de físicos
    - phdict: diccionario que mapea nombres a IDs
    """
    for physicist in physicists:
        physicist_id = phdict[physicist]
        col_name = f'av_{physicist}'
        
        for date in acppadf.index:
            acppadf.at[date, col_name] = physicist_acum_availability(ac_df, physicist_id, date)
    
    return acppadf

def add_physicist_norm_activity(acppadf, physicists, phdict):
    for physicist in physicists:
        physicist_id = phdict[physicist]
        col_name = f'nac_{physicist}'
        acppadf[col_name] = acppadf[physicist] / acppadf[f'av_{physicist}']
        continue

    return acppadf