"""Daily public data refresh. No API keys or third-party packages required."""
import json, os, sys, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
NOW=datetime.now(ZoneInfo('Asia/Seoul'))

def request(url):
    req=urllib.request.Request(url,headers={'User-Agent':'BusanHanilLionsWebsite/1.0'})
    with urllib.request.urlopen(req,timeout=25) as response:
        return response.read()

def save(name,data):
    path=ROOT/'data'/name
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)

failures=[]
weather={'updated_at':NOW.isoformat(),'cities':{}}
# Preserve the requested Oct 1–8 window once it becomes historical, and include
# recent days so today's/yesterday's cards keep working after that week.
for name,(lat,lon) in {'busan':(35.1796,129.0756),'seoul':(37.5665,126.978),'daegu':(35.8714,128.6014)}.items():
    try:
        cutoff=(NOW.date()-timedelta(days=5)).isoformat()
        end='2026-10-08'
        historical=end<cutoff
        base='https://archive-api.open-meteo.com/v1/archive' if historical else 'https://api.open-meteo.com/v1/forecast'
        if end>NOW.date().isoformat():
            start=(NOW.date()-timedelta(days=7)).isoformat(); end=NOW.date().isoformat()
        else: start='2026-10-01'
        params={'latitude':lat,'longitude':lon,'daily':'temperature_2m_max,temperature_2m_min','timezone':'Asia/Seoul','start_date':start,'end_date':end}
        result=json.loads(request(base+'?'+urllib.parse.urlencode(params)))
        daily=result['daily']
        if historical:
            params['start_date']=(NOW.date()-timedelta(days=7)).isoformat();params['end_date']=NOW.date().isoformat()
            recent=json.loads(request('https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode(params)))['daily']
            combined={d:(daily['temperature_2m_min'][i],daily['temperature_2m_max'][i]) for i,d in enumerate(daily['time'])}
            combined.update({d:(recent['temperature_2m_min'][i],recent['temperature_2m_max'][i]) for i,d in enumerate(recent['time'])})
            daily={'time':sorted(combined),'temperature_2m_min':[combined[d][0] for d in sorted(combined)],'temperature_2m_max':[combined[d][1] for d in sorted(combined)]}
        if not daily.get('time'):raise ValueError('No weather dates')
        weather['cities'][name]={'daily':daily}
    except Exception as e: failures.append(f'weather/{name}: {e}')
# Only replace the cache when all cities succeeded; never label old data as fresh.
if len(weather['cities'])==3:save('weather.json',weather)
try:
    query='(site:busan.com OR site:lionsclubs.org OR site:lc355a.or.kr) (부산 OR 라이온스 OR 봉사 OR 복지) when:1d'
    url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query,'hl':'ko','gl':'KR','ceid':'KR:ko'})
    root=ET.fromstring(request(url));items=[]
    for item in root.findall('./channel/item')[:8]:
        source=item.find('source'); source_url=source.get('url','') if source is not None else ''
        if urllib.parse.urlparse(source_url).hostname not in {'busan.com','www.busan.com','lionsclubs.org','www.lionsclubs.org','lc355a.or.kr','www.lc355a.or.kr'}:continue
        items.append({'title':item.findtext('title',''),'url':item.findtext('link',''),'published_at':item.findtext('pubDate',''),'source':source.text if source is not None else ''})
    save('news.json',{'updated_at':NOW.isoformat(),'items':items,'source':'Google News RSS — linked publisher headlines only'})
except Exception as e:failures.append(f'news: {e}')
for error in failures: print(error,file=sys.stderr)
if failures:sys.exit(1)
print('Weather and headline caches updated:',NOW.isoformat())
