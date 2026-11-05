#!/usr/bin/env python3
"""Public-repo, self-contained JPX Prime breadth updater.

Reads/writes ONLY public stock-market aggregates in jpfg-breadth.json.
Uses official JPX auction/regular-way daily PDF and a strict, independently tested
Prime-only parser. No credentials; no internal KABU NOTE API; no portfolio data.
"""
from __future__ import annotations

from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import importlib.util
import json
import time
import urllib.error

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/"jpfg-breadth.json"
PARSER_PATH=BASE/"scripts/jpx_prime_parser.py"
MOD=importlib.util.spec_from_file_location("jpx_prime_parser",PARSER_PATH)
PARSER=importlib.util.module_from_spec(MOD)
MOD.loader.exec_module(PARSER)

MAX_STORED=90
MAX_LOOKBACK_DAYS=12

def main():
    original=json.loads(OUT.read_text(encoding="utf8"))
    if (original.get("market")!="TSE_PRIME" or
        original.get("unchangedExcluded") is not True or
        not isinstance(original.get("rows"),list)):
        raise ValueError("Untrusted existing market JSON contract")
    existing={}
    for row in original["rows"]:
        if row.get("complete") is not True:
            continue
        date=row.get("date")
        if not date or not isinstance(date,str):
            raise ValueError("Invalid date in existing feed")
        counts=[row.get(k) for k in ("advancers","decliners","upVolume","downVolume")]
        if any(not isinstance(v,(float,int)) or v<=0 for v in counts):
            raise ValueError("Invalid value in existing feed")
        existing[date]=row
    if len(existing)<25: raise ValueError("Existing public feed has fewer than 25 complete market days")
    today=datetime.now(ZoneInfo("Asia/Tokyo")).date()
    fetches=0
    new=0
    not_published=0
    failed=[]
    # JPX usually publishes the TSE stock quotations PDF after the session.
    for offset in range(0,MAX_LOOKBACK_DAYS+1):
        day=today-timedelta(days=offset)
        if day.weekday()>=5: continue
        key=day.isoformat()
        if key in existing: continue
        daypart=day.strftime("%Y%m%d")
        url=(f"https://www.jpx.co.jp/automation/markets/statistics-equities/"
             f"daily/files/{daypart[:6]}/stq_{daypart}.pdf")
        try:
            with PARSER.fetch(url) as pdf:
                values=PARSER.extract(pdf,day)
            if values.get("complete") is not True:
                print(f"{key} official PDF was incomplete, keeping existing data",flush=True)
                continue
            counts=values["counts"]
            volumes=values["volumeThousandShares"]
            row={"date":key,"advancers":counts["up"],"decliners":counts["down"],
                 "upVolume":volumes["up"],"downVolume":volumes["down"],"complete":True}
            if row["advancers"]<=0 or row["decliners"]<=0 or row["upVolume"]<=0 or row["downVolume"]<=0:
                raise ValueError("Nonpositive official market observations")
            existing[key]=row
            new+=1
            print(f"Verified JPX TSE Prime {key}: +{row['advancers']} -{row['decliners']}, "
                  f"volume+={row['upVolume']}, volume-={row['downVolume']}",flush=True)
        except urllib.error.HTTPError as exc:
            if exc.code==404:
                not_published+=1
                print(f"{key}: no official PDF yet (404)",flush=True)
            elif exc.code in (403,429):
                raise RuntimeError("JPX blocked or throttled the feed; stopped safely") from exc
            else:
                failed.append(f"{key}: HTTP {exc.code}")
        except Exception as exc:
            failed.append(f"{key}: {type(exc).__name__}: {exc}")
        fetches+=1
        time.sleep(.75)
    rows=sorted(existing.values(),key=lambda x:x["date"])[-MAX_STORED:]
    if len(rows)<25: raise ValueError("25 complete market days are mandatory")
    for r in rows:
        if r["complete"] is not True: raise ValueError("Incomplete day cannot be public")
    out={
       "market":"TSE_PRIME",
       "source":"Japan Exchange Group official Prime auction regular-way stock quotations; aggregated market statistics",
       "unchangedExcluded":True,"rows":rows
    }
    new_text=json.dumps(out,ensure_ascii=False,indent=2)+"\n"
    if new:
        OUT.write_text(new_text,encoding="utf8")
    print("JPX public feed:",len(rows),"verified historical days;",new,
          "newly collected;",not_published,"not yet published;",len(failed),"errors")
    if failed:
        for f in failed: print("WARNING:",f,flush=True)
        raise RuntimeError("One or more official report reads failed; valid observations preserved")
    print("Safe public feed latest date:",rows[-1]["date"])

if __name__=="__main__": main()
