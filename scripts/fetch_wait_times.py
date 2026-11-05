#!/usr/bin/env python3
"""DisneyRealの待ち時間ページを1回だけ取得し wait-times.json を生成する(GitHub Actions用)。
安全設計: 実行時にrobots.txtを確認(不許可なら中止)/1回の実行で1ページのみ/CAPTCHA等の回避はしない/
失敗・件数不足・形式異常のときは既存のwait-times.jsonに触れず終了コード!=0で終わる。
注意: 実HTMLのDOMは未確認。想定=待ち時間カードは <a href=".../attraction/xx_name.html" title="〇〇の待ち時間"> で、
カード内テキスト末尾が「朝 昼 夜」の平均3数値(変換済みテキストで確認)。--debug で生HTMLを debug/ に保存し検証できる。"""
import json,re,sys,os,datetime,urllib.request,urllib.robotparser
from html.parser import HTMLParser
BASE='https://disneyreal.asumirai.info'
PAGE=BASE+'/realtime/disneysea-wait-today.html'
REST=BASE+'/realtime/disneysea-restaurant-today.html'
UA='DisneySeaPersonalApp/0.2 (personal, low-frequency)'
OUT='wait-times.json'
JST=datetime.timezone(datetime.timedelta(hours=9))

class P(HTMLParser):
    def __init__(s):
        super().__init__(); s.items=[]; s.cur=None
    def handle_starttag(s,t,a):
        if t=='a':
            d=dict(a); h=d.get('href') or ''
            m=re.search(r'/attraction/([a-z]{2})_([a-z0-9_]+)\.html',h)
            s.cur={'slug':m.group(1)+'_'+m.group(2),'area':m.group(1),'title':d.get('title') or '','t':[]} if m else None
    def handle_data(s,d):
        if s.cur is not None: s.cur['t'].append(d)
    def handle_endtag(s,t):
        if t=='a' and s.cur is not None: s.items.append(s.cur); s.cur=None

def parse(html):
    p=P(); p.feed(html)
    stop={i['slug'] for i in p.items if ' '.join(i['t']).strip().startswith('休止アトラクション')}
    out={}
    for i in p.items:
        if not i['title'].endswith('の待ち時間') or i['slug'] in out: continue
        tx=' '.join(' '.join(i['t']).split())
        if i['slug'] in stop: st='stop'
        elif '閉園中' in tx: st='closed'
        elif re.search(r'休止|中止',tx): st='stop'
        else: st='open'
        m=re.search(r'(\d+)\s*分',tx); wait=int(m.group(1)) if (m and st=='open') else None
        v=re.search(r'(\d+|-)\s+(\d+|-)\s+(\d+|-)\s*$',tx)
        avg=[None if x=='-' else int(x) for x in v.groups()] if v else None
        dpa=('sale_none' if '販売なし' in tx else 'other') if 'DPA' in tx else None
        out[i['slug']]={'slug':i['slug'],'name':i['title'][:-len('の待ち時間')],'area':i['area'],'status':st,'wait':wait,'avg':avg,'dpa':dpa,'raw':tx[:200]}
    return list(out.values())

def get(url):
    r=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':UA}),timeout=20)
    if r.status!=200: raise RuntimeError('HTTP %s'%r.status)
    return r.read().decode('utf-8','replace')

def main():
    rp=urllib.robotparser.RobotFileParser(BASE+'/robots.txt'); rp.read()
    if not rp.can_fetch(UA,PAGE): print('robots.txtで不許可のため中止'); return 2
    html=get(PAGE); items=parse(html)
    if '--debug' in sys.argv:
        os.makedirs('debug',exist_ok=True); open('debug/page.html','w').write(html)
        if rp.can_fetch(UA,REST): open('debug/restaurant.html','w').write(get(REST))
    if len(items)<10: print('取得件数不足(%d件)。構造が想定と違う可能性。既存JSONは変更しません'%len(items)); return 1
    closed=sum(1 for i in items if i['status']=='closed')
    j={'schema':1,'generated_at':datetime.datetime.now(JST).isoformat(timespec='seconds'),'source':PAGE,
       'park_status':'closed' if closed>len(items)/2 else 'open','attractions':items,'restaurants':[]}
    json.dump(j,open(OUT+'.tmp','w'),ensure_ascii=False,indent=1); os.replace(OUT+'.tmp',OUT)
    print('OK',len(items),'件',j['park_status']); return 0
if __name__=='__main__': sys.exit(main())
