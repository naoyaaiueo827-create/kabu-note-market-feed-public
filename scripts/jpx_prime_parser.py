#!/usr/bin/env python3
"""JPX official auction-trade Prime stock breadth and up/down volume. No JPFG score."""
import datetime as dt
import json
import re
import urllib.request
import urllib.parse
from decimal import Decimal
from pathlib import Path
import fitz

INDEX=Path("data/staging-jpx-reports.json")
OUTPUT=Path("data/staging-jpx-prime-breadth.json")
CODE=re.compile(r"^(?:\d{4}|\d{3}[A-Z])$")
NUM=re.compile(r"^[+-]?\d[\d,]*(?:\.\d+)?$")

def number_at(row, left, right):
    vals=[w[4] for w in row if left<=w[2]<right and NUM.fullmatch(str(w[4]))]
    return Decimal(vals[0].replace(",","")) if len(vals)==1 else None

def extract(pdf,date):
    txt=pdf[0].get_text("text")
    if "Stock Quotations" not in txt or "Prime Market" not in txt:
        raise ValueError("Unexpected PDF title/market")
    if not re.search(rf"{date.year}年\s*{date.month}月\s*{date.day}日",txt):
        raise ValueError("Report date mismatch")
    codes=set()
    counts={"up":0,"down":0,"unchanged":0,"missing":0}
    vols={"up":Decimal(0),"down":Decimal(0),"unchanged":Decimal(0)}
    examples={k:[] for k in counts}
    standard_page=None
    pages=0
    for pno,page in enumerate(pdf,1):
        if pno>101: raise ValueError("Standard Market heading not found")
        text=page.get_text("text")
        if not re.search(r"\b1-\s*\d+\b",text[:130]):
            raise ValueError("Unexpected break in auction section")
        words=page.get_text("words",sort=False)
        headings=[w[1] for w in words if "スタンダード市場" in w[4] or (w[4]=="Standard" and "Standard Market" in text)]
        cutoff=min(headings) if headings else 10000
        pages+=1
        for w in words:
            if not (65<=w[0]<=90 and 134<=w[1]<cutoff-1 and CODE.fullmatch(str(w[4]))):
                continue
            symbol=w[4]
            if symbol in codes: raise ValueError("Repeated Prime code: "+symbol)
            codes.add(symbol)
            row=[v for v in words if abs(v[1]-w[1])<2.5]
            change=number_at(row,850,915)
            volume=number_at(row,1005,1060)
            if change is None or volume is None: label="missing"
            elif volume<0: raise ValueError("Negative volume: "+symbol)
            elif change>0: label="up"
            elif change<0: label="down"
            else: label="unchanged"
            counts[label]+=1
            if label!="missing": vols[label]+=volume
            if len(examples[label])<3:
                examples[label].append({"symbol":symbol,"change":str(change) if change is not None else None,"volumeThousandShares":str(volume) if volume is not None else None,"page":pno})
        if headings:
            standard_page=pno
            break
    n=len(codes)
    if not standard_page or not (45<=standard_page<=85):
        raise ValueError("Market boundary not safely identified")
    if not (1300<=n<=2000) or sum(counts.values())!=n:
        raise ValueError(f"Unexpected Prime issues count: {n}")
    if counts["up"]+counts["down"]<500 or counts["missing"]>n*.12:
        raise ValueError(f"Insufficient validated price/volume rows: {counts}")
    return {
        "date":date.isoformat(),"status":"complete" if counts["missing"]==0 else "partial",
        "complete":counts["missing"]==0,
        "market":"Prime domestic stocks, auction regular way",
        "counts":{**counts,"totalIssues":n},
        "volumeThousandShares":{k:float(v) for k,v in vols.items()},
        "volumeUnit":"thousand shares as printed on official JPX report",
        "pagesProcessed":pages,"standardMarketStartsAtPage":standard_page,
        "diagnosticExamples":examples,
        "method":"PyMuPDF word-row coordinates, net change x850..907, trading volume right-edge x1005..1060; no ETFs, no ToSTNeT"
    }

def fetch(url):
    u=urllib.parse.urlparse(url)
    if u.scheme!="https" or u.hostname!="www.jpx.co.jp" or not re.fullmatch(r"/automation/markets/statistics-equities/daily/files/\d{6}/stq_\d{8}\.pdf",u.path):
        raise ValueError("Untrusted JPX source URL")
    req=urllib.request.Request(url,headers={"User-Agent":"KabuNote-PrimeBreadth/1.0","Accept":"application/pdf"})
    with urllib.request.urlopen(req,timeout=60) as response:
        data=response.read(25_000_001)
    if len(data)>25_000_000 or not data.startswith(b"%PDF-"):
        raise ValueError("PDF signature or file-size validation failed")
    return fitz.open(stream=data,filetype="pdf")

def main():
    listing=json.loads(INDEX.read_text(encoding="utf8"))
    reports=listing.get("reports",[])[:4]
    if not reports: raise ValueError("No verified PDF sources")
    old=json.loads(OUTPUT.read_text(encoding="utf8")) if OUTPUT.exists() else {}
    known={x["date"]:x for x in old.get("observations",[])}
    successes=0
    failures=[]
    for item in reports:
        date=dt.date.fromisoformat(item["marketDate"])
        try:
            with fetch(item["url"]) as pdf:
                result=extract(pdf,date)
            result["sourceUrl"]=item["url"]
            known[result["date"]]=result
            successes+=1
            print(f"{date}: Prime issues={result['counts']['totalIssues']}; rising={result['counts']['up']}, falling={result['counts']['down']}, unchanged={result['counts']['unchanged']}, missing={result['counts']['missing']}; upVol={result['volumeThousandShares']['up']}, downVol={result['volumeThousandShares']['down']} (thousand shares)")
        except Exception as error:
            failures.append({"date":date.isoformat(),"reason":str(error)})
            print(f"FAILED {date}: {type(error).__name__}: {error}")
    if successes==0: raise ValueError("No PDF parsed successfully; previous output preserved")
    observations=sorted(known.values(),key=lambda x:x["date"])[-90:]
    cache={
        "schemaVersion":1,"fetchedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        "source":"Japan Exchange Group official Stock Quotations PDF",
        "lastVerifiedDate":observations[-1]["date"],"newValidReports":successes,
        "interpretation":"Official Prime breadth and traded volume INPUTS only; no five-factor JP Fear & Greed score",
        "observations":observations,"failures":failures
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(cache,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(f"Saved {len(observations)} official observations")
    if failures: raise RuntimeError("Partial data collection failure; see cache and logs")

if __name__=="__main__":
    main()
