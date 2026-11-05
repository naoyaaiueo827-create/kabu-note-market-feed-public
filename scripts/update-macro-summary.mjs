#!/usr/bin/env node
/**
 * Public, non-personal macro MARKET DATA snapshot from FRED's graph CSV.
 * This is deliberately not a KABU NOTE account/portfolio cache.
 *
 * No personal positions, trade records, service tokens, or full-price history.
 * Only independently sourced latest publicly-reported observations.
 */
import {readFile,writeFile} from 'node:fs/promises';

const output='macro-summary.json';
const source='Federal Reserve Bank of St. Louis FRED';
const indicators=[
 {id:'DGS10',name:'米国10年国債利回り',unit:'%'}, 
 {id:'DGS2',name:'米国2年国債利回り',unit:'%'},
 {id:'VIXCLS',name:'VIX',unit:'index'},
 {id:'DFF',name:'実効FF金利',unit:'%'},
 {id:'DEXJPUS',name:'ドル円（米ドル当たり円）',unit:'JPY/USD'},
 {id:'UNRATE',name:'米国失業率',unit:'%'},
 {id:'IRLTLT01JPM156N',name:'日本10年国債利回り（月次平均）',unit:'% monthly'},
 {id:'LRHUTTTTJPM156S',name:'日本失業率（月次・季節調整）',unit:'% monthly'},
 {id:'JPNPRMNTO01GYSAM',name:'日本製造業生産前年比（月次）',unit:'% y/y'},
 {id:'JPNRGDPEXP',name:'日本実質GDP（四半期）',unit:'billions chained 2015 JPY'},
 {id:'NIKKEI225',name:'日経平均株価（取引所終値・FRED収録）',unit:'JPY/index'}
];
const now=new Date().toISOString();
const today=now.slice(0,10);
const previous=await readFile(output,'utf8').then(JSON.parse).catch(()=>null);
const cache=new Map((previous?.indicators||[]).filter(x=>x.id).map(x=>[x.id,x]));
const rows=[];
let succeeded=0;
let errors=[];
for (const s of indicators) {
  const url=new URL('https://fred.stlouisfed.org/graph/fredgraph.csv');
  url.searchParams.set('id',s.id);
  try{
    const response=await fetch(url,{redirect:'error',signal:AbortSignal.timeout(60000),
      headers:{'User-Agent':'KabuNotePublicMarketReference/1.0'}});
    if(!response.ok)throw Error('HTTP '+response.status);
    const csv=await response.text();
    if(csv.length<30 || csv.length>12000000)throw Error('Unexpected source length');
    const lines=csv.trim().split(/\r?\n/);
    const header=lines.shift()?.replace(/^\uFEFF/,'');
    if(header!=='observation_date,'+s.id && header!=='DATE,'+s.id)throw Error('Unexpected CSV headers');
    let last;
    let valid=0;
    for(const line of lines){
      const [date,v]=line.split(',');
      if(!/^\d{4}-\d{2}-\d{2}$/.test(date||'')|| !/^-?\d+(?:\.\d+)?$/.test(v||''))continue;
      const value=Number(v);
      if(!Number.isFinite(value)||date>today)continue;
      valid++;
      last={date,value};
    }
    if(valid<3||!last)throw Error('Insufficient source observations');
    const old=cache.get(s.id);
    if(old?.latest?.date && last.date<old.latest.date)throw Error('Source observation date regressed');
    rows.push({...s,source,sourceUrl:url.href,latest:last,verifiedAt:now,dataStatus:'fresh_fetch'});
    succeeded++;
    console.log(s.id,'->',last.date,last.value);
  }catch(e){
    const old=cache.get(s.id);
    errors.push({id:s.id,reason:String(e.message)});
    if(old?.latest?.date){
      rows.push({...s,source,sourceUrl:url.href,latest:old.latest,verifiedAt:old.verifiedAt||null,dataStatus:'cached_after_fetch_error'});
      console.error(s.id,'failed; retained explicitly stale cache');
    }else{
      rows.push({...s,source,sourceUrl:url.href,latest:null,verifiedAt:null,dataStatus:'unavailable'});
      console.error(s.id,'failed and unavailable');
    }
  }
}
if(succeeded===0)throw Error('No current source data verified; existing JSON retained');
const data={
 schemaVersion:1,
 kind:'market-only-latest-public-reference; NOT KABU NOTE backend state',
 generatedAt:now,
 status:errors.length?'partial':'complete',
 source,
 indicators:rows,
 sourceErrors:errors,
 warnings:[
  'Values are latest published observations, not necessarily current trading prices.',
  'Series frequency differs; Japanese 10-year yield in this feed is a monthly average.',
  'This endpoint is not currently consumed by the KABU NOTE application; app integration requires an authorized reader implementation.',
  'No trade signals, account data, or user-private values.'
 ]
};
await writeFile(output,JSON.stringify(data,null,2)+'\n');
console.log('Prepared public FRED-only macro snapshot',succeeded+'/'+indicators.length);
if(errors.length)process.exitCode=1;
