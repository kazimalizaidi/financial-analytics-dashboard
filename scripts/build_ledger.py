"""Build the HelmQuant ledger from the UCI "Online Retail II" dataset.

Usage:  python scripts/build_ledger.py online_retail_II.xlsx data/helmquant_ledger.csv
Input : the original UCI workbook (two sheets: Year 2009-2010, Year 2010-2011).
Output: one CSV ledger (Date, Description, Category, Type, Account, Amount, Status, Source).
Rules : see data/README.md. 'Real' rows are aggregated from the source; 'Modelled' rows are assumptions.
"""
import sys, json, re
import pandas as pd, numpy as np
SRC_XLSX, OUT_CSV = sys.argv[1], sys.argv[2]
_sheets = pd.read_excel(SRC_XLSX, sheet_name=None)
_a, _b = list(_sheets.values())[0], list(_sheets.values())[1]
# the two sheets overlap on 1-9 Dec 2010 (identical rows): keep one copy
df = pd.concat([_a, _b[_b.InvoiceDate > _a.InvoiceDate.max()]], ignore_index=True)
df['Invoice']=df.Invoice.astype(str).str.strip(); df['StockCode']=df.StockCode.astype(str).str.strip()
df['Description']=df.Description.fillna('').astype(str).str.upper().str.strip()
df['amt']=(df.Quantity*df.Price).round(2)
df['d']=df.InvoiceDate.dt.normalize()
SRC_ROWS=len(df)
# --- cut-off: whole months only (drops 1-9 Dec 2011, a partial month)
LAST=pd.Timestamp('2011-11-30')
df=df[df.d<=LAST].copy()
CUT_ROWS=len(df)

# ---------- classification ----------
TEST=['PADS','SP1002','TEST001','TEST002']              # test / dummy lines, dropped
SHIP=['POST','DOT','C2']                                 # carriage billed to customers
def classify(r):
    sc,inv,a=r.StockCode,r.Invoice,r.amt
    if sc in TEST or a==0: return ('drop',None)
    if sc in SHIP: return ('Income','Shipping & Other Income') if a>0 else ('Expense','Bad Debt & Adjustments')
    if sc=='AMAZONFEE': return ('Expense','Marketplace Fees') if a<0 else ('Income','Shipping & Other Income')
    if sc=='BANK CHARGES': return ('Expense','Bank Charges') if a<0 else ('Income','Shipping & Other Income')
    if sc in ('B','D','S','CRUK','M','ADJUST','ADJUST2','m'):
        return ('Expense','Bad Debt & Adjustments') if a<0 else ('Income','Shipping & Other Income')
    if inv.startswith('C') or a<0: return ('Expense','Returns & Credit Notes')
    return ('Income','PRODUCT')
cl=df.apply(classify,axis=1,result_type='expand'); df['type']=cl[0]; df['cat']=cl[1]
dropped=df[df.type=='drop']; df=df[df.type!='drop'].copy()

# product groups by keyword (first match wins)
RULES=[('Gifts, Cards & Seasonal',r'CHRISTMAS|XMAS|CARD|WRAP|GIFT|PARTY|EASTER|HALLOWEEN|TOY|GAME|PUZZLE|DOLL|BALLOON|BUNTING|STICKER|RIBBON|ADVENT|SANTA|REINDEER|SNOW|TREE|STOCKING|BIRTHDAY|WEDDING|CRAFT|PENCIL|NOTEBOOK|STATIONERY|PEN\b'),
       ('Bags & Storage',r'\bBAG\b|BAGS|BOX|CASE|BASKET|TIN\b|TINS|STORAGE|TRUNK|CHEST|DRAWER|HOLDER|ORGANI[SZ]ER|HOOK|RACK|SHELF|CRATE|JAR\b|LUNCH'),
       ('Kitchen & Dining',r'MUG|CUP|BOWL|PLATE|TEA\b|TEAPOT|CAKE|NAPKIN|BOTTLE|KITCHEN|SPOON|FORK|KNIFE|TRAY|APRON|BAKING|COOK|SALT|PEPPER|DISH|GLASS|COASTER|PLACEMAT|CUTLERY|DOILIES|TEACUP|SAUCER|JUG|CAKESTAND|PICNIC|EGG'),
       ]
def pgroup(t):
    for g,pat in RULES:
        if re.search(pat,t): return g
    return 'Home & Decor'
m=df.cat=='PRODUCT'
df.loc[m,'cat']=df.loc[m,'Description'].map(pgroup)

REGION={'United Kingdom':'UK'}
EU={'EIRE','Netherlands','Germany','France','Spain','Switzerland','Belgium','Portugal','Sweden','Italy','Norway','Finland','Denmark','Austria','Channel Islands','Cyprus','Greece','Poland','Malta','Iceland','Lithuania','Czech Republic','European Community','Lebanon','Bulgaria','Hungary','Romania'}
def region(c): return 'UK Sales' if c=='United Kingdom' else ('Europe Sales' if c in EU else 'Export Sales')

rows=[]
# ---- income: daily x product group (+ shipping & other)
inc=df[df.type=='Income']
g=inc.groupby(['d','cat']).agg(amt=('amt','sum'),inv=('Invoice','nunique'),lines=('amt','size')).reset_index()
for r in g.itertuples():
    if r.cat=='Shipping & Other Income':
        desc=f"Carriage & manual invoices ({r.lines} lines)"
    else:
        desc=f"Daily sales - {r.cat} ({r.inv} invoices)"
    rows.append((r.d,desc,r.cat,'Income','Online Sales',round(r.amt,2),'Real','real'))
# ---- real expenses
ex=df[df.type=='Expense'].copy(); ex['amt']=-ex.amt   # store positive; Type carries the sign
for cat in ['Returns & Credit Notes']:
    g=ex[ex.cat==cat].groupby('d').agg(amt=('amt','sum'),inv=('Invoice','nunique')).reset_index()
    for r in g.itertuples(): rows.append((r.d,f"Returns & credit notes ({r.inv} credit notes)",cat,'Expense','Operating Account',round(r.amt,2),'Real','real'))
for cat,label in [('Marketplace Fees','Amazon marketplace fee'),('Bank Charges','Bank charges')]:
    for r in ex[ex.cat==cat].itertuples(): rows.append((r.d,f"{label} - inv {r.Invoice}",cat,'Expense','Operating Account',round(r.amt,2),'Real','real'))
a=ex[ex.cat=='Bad Debt & Adjustments']
big=a[a.StockCode=='B']
for r in big.itertuples(): rows.append((r.d,f"Adjust bad debt - inv {r.Invoice}",'Bad Debt & Adjustments','Expense','Operating Account',round(r.amt,2),'Real','real'))
rest=a[a.StockCode!='B'].groupby('d').agg(amt=('amt','sum'),n=('amt','size')).reset_index()
for r in rest.itertuples(): rows.append((r.d,f"Manual adjustments, discounts & samples ({r.n} lines)",'Bad Debt & Adjustments','Expense','Operating Account',round(r.amt,2),'Real','real'))

# region split for the Account column of income rows: keep 'Online Sales' (daily rollup) -> region detail kept in data/ CSV only
led=pd.DataFrame(rows,columns=['Date','Description','Category','Type','Account','Amount','Source','k'])

# ---------- modelled overheads (clearly labelled) ----------
ASSUME=dict(cogs_pct=0.62, mkt_pct=0.03, salary_2010=115000, salary_2011=122000, rent=24000)
months=pd.period_range('2009-12','2011-11',freq='M')
prod_rev=led[(led.Type=='Income')&(led.Category!='Shipping & Other Income')].copy(); prod_rev['m']=prod_rev.Date.dt.to_period('M')
pm=prod_rev.groupby('m').Amount.sum()
mod=[]
for p in months:
    last_day=led[led.Date.dt.to_period('M')==p].Date.max()
    first_day=p.to_timestamp()
    ds=led[led.Date.dt.to_period('M')==p].Date.min()
    sal=ASSUME['salary_2010'] if p.year<=2010 else ASSUME['salary_2011']
    lab=p.strftime('%b %Y')
    mod.append((ds,f"Payroll - {lab} (modelled)",'Salaries','Expense','Operating Account',float(sal),'Modelled','a'))
    mod.append((ds,f"Warehouse rent & utilities - {lab} (modelled)",'Rent & Utilities','Expense','Operating Account',float(ASSUME['rent']),'Modelled','a'))
    mod.append((last_day,f"Cost of goods sold - {lab} (modelled, {int(ASSUME['cogs_pct']*100)}% of product sales)",'Cost of Goods','Expense','Operating Account',round(pm[p]*ASSUME['cogs_pct'],2),'Modelled','0'))
    mod.append((last_day,f"Marketing & promotions - {lab} (modelled, {int(ASSUME['mkt_pct']*100)}% of product sales)",'Marketing','Expense','Operating Account',round(pm[p]*ASSUME['mkt_pct'],2),'Modelled','0'))
led=pd.concat([led,pd.DataFrame(mod,columns=led.columns)],ignore_index=True)
# stable sort: date, modelled before real within a day
led['o']=led.k.map({'0':0,'a':1,'real':2})
led=led.sort_values(['Date','o','Type','Category','Description'],kind='mergesort').drop(columns=['k','o']).reset_index(drop=True)
led['Status']='Completed'
led=led[['Date','Description','Category','Type','Account','Amount','Status','Source']]
led.to_csv(OUT_CSV, index=False, date_format='%Y-%m-%d')
print('wrote', OUT_CSV, len(led), 'rows')
