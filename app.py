from datetime import datetime, timedelta
import json
import os
from flask import Flask, jsonify, send_file
from flask_cors import CORS
import requests
import xml.etree.ElementTree as ET

app = Flask(__name__)
CORS(app)

# 1. 서울시 API 키
SEOUL_API_KEY = "626542794374746e353657776b5577"

# 2. 공공데이터포털(문화포털) 서비스키
CULTURE_API_KEY = "fc9e72622a547b6e71d08e379172588be1ab895cea97b9ea9beebfc35dc44dc1"


# -------------------------------------------------------------
# 🌐 [추가됨] 루트(/) 주소로 접속했을 때 index.html 화면을 보여주는 설정
# -------------------------------------------------------------
@app.route('/')
def home():
    # 같은 폴더 내의 index.html을 직접 열어줍니다.
    return send_file('index.html')


def fetch_seoul_api():
    """1. 서울시 문화행사 API"""
    url = f"http://openapi.seoul.go.kr:8088/{SEOUL_API_KEY}/json/culturalEventInfo/1/200/"
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json().get("culturalEventInfo", {}).get("row", [])
    except Exception as e:
        print(f"⚠️ 서울시 API 수집 예외: {e}")
    return []


def fetch_culture_events():
    """2. 문화포털 기획전시 API (/realm)"""
    url = "https://apis.data.go.kr/B553457/nopenapi/rest/publicperformancedisplays/realm"
    today = datetime.now()
    from_date = today.strftime("%Y%m%d")
    to_date = (today + timedelta(days=90)).strftime("%Y%m%d")

    params = {
        "serviceKey": CULTURE_API_KEY,
        "realmCode": "D000",
        "sido": "서울",
        "from": from_date,
        "to": to_date,
        "cPage": "1",
        "rows": "100",
    }

    try:
        res = requests.get(url, params=params, timeout=5)
        print(f"[문화포털 전시 API] 응답 코드: {res.status_code}")

        if res.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in res.text:
                print("❌ 문화포털 키 인증 실패: 서비스키를 확인하세요")
                return []

            events = []
            try:
                root = ET.fromstring(res.content)
                items = root.findall(".//perforList") or root.findall(".//item")
                for item in items:
                    title = item.findtext("title") or item.findtext("TITLE") or ""
                    place = item.findtext("place") or item.findtext("PLACE") or ""
                    s_date = item.findtext("startDate") or ""
                    e_date = item.findtext("endDate") or ""

                    if title:
                        events.append({
                            "TITLE": title,
                            "PLACE": place,
                            "DATE": f"{s_date} ~ {e_date}" if s_date else "일정 참조",
                            "SOURCE": "문화포털(전시)"
                        })
            except ET.ParseError as pe:
                print(f"⚠️ XML 파싱 에러 (기획전시): {pe}")
            return events
    except Exception as e:
        print(f"⚠️ 문화포털 전시 API 수집 예외: {e}")
    return []


def fetch_culture_museums():
    """3. 문화포털 미술관 시설 API (/museum)"""
    url = "https://apis.data.go.kr/B553457/nopenapi/rest/cultureartspaces/museum"
    params = {
        "serviceKey": CULTURE_API_KEY,
        "sido": "서울",
        "cPage": "1",
        "rows": "100",
    }

    try:
        res = requests.get(url, params=params, timeout=5)
        print(f"[문화포털 미술관 API] 응답 코드: {res.status_code}")

        if res.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in res.text:
                return []

            museums = []
            try:
                root = ET.fromstring(res.content)
                items = root.findall(".//perforList") or root.findall(".//item")
                for item in items:
                    title = item.findtext("culName") or item.findtext("title") or ""
                    place = item.findtext("addr") or item.findtext("place") or ""

                    if title:
                        museums.append({
                            "TITLE": f"[미술관] {title}",
                            "PLACE": place or title,
                            "DATE": "상설/기획전 운영 중",
                            "SOURCE": "문화시설DB(미술관)"
                        })
            except ET.ParseError as pe:
                print(f"⚠️ XML 파싱 에러 (미술관): {pe}")
            return museums
    except Exception as e:
        print(f"⚠️ 문화포털 미술관 API 수집 예외: {e}")
    return []


def fetch_ticket_discounts():
    """4. 문화릴레이티켓 할인 API (/ticketdiscounts/list)"""
    url = "https://apis.data.go.kr/B553457/nopenapi/rest/ticketdiscounts/list"
    params = {
        "serviceKey": CULTURE_API_KEY,
        "cPage": "1",
        "rows": "100",
    }

    try:
        res = requests.get(url, params=params, timeout=5)
        print(f"[문화릴레이 API] 응답 코드: {res.status_code}")

        if res.status_code == 200:
            if "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" in res.text:
                return []

            discounts = []
            try:
                root = ET.fromstring(res.content)
                items = root.findall(".//perforList") or root.findall(".//item")
                for item in items:
                    title = item.findtext("title") or ""
                    place = item.findtext("place") or ""
                    s_date = item.findtext("startDate") or ""
                    e_date = item.findtext("endDate") or ""

                    if title:
                        discounts.append({
                            "TITLE": f"🎟️ [할인] {title}",
                            "PLACE": place,
                            "DATE": f"{s_date} ~ {e_date}" if s_date else "할인 진행 중",
                            "SOURCE": "문화릴레이티켓"
                        })
            except ET.ParseError as pe:
                print(f"⚠️ XML 파싱 에러 (할인): {pe}")
            return discounts
    except Exception as e:
        print(f"⚠️ 문화릴레이티켓 API 수집 예외: {e}")
    return []


@app.route("/api/exhibitions", methods=["GET"])
def get_exhibitions():
    seoul_data = fetch_seoul_api()
    culture_event_data = fetch_culture_events()
    culture_museum_data = fetch_culture_museums()
    discount_data = fetch_ticket_discounts()

    total_data = seoul_data + culture_event_data + culture_museum_data + discount_data

    print("\n" + "=" * 60)
    print("📡 [4중 크롤링/API 동기화 완료 리포트]")
    print(f" 1️⃣ 서울시 문화행사: {len(seoul_data)}건")
    print(f" 2️⃣ 문화포털 기획전시: {len(culture_event_data)}건")
    print(f" 3️⃣ 문화포털 미술관 시설: {len(culture_museum_data)}건")
    print(f" 4️⃣ 문화릴레이 할인정보: {len(discount_data)}건")
    print(f" 🎨 총합 데이터: {len(total_data)}건")
    print("=" * 60 + "\n")

    return jsonify({"status": "success", "data": total_data})


if __name__ == "__main__":
    app.run(port=5000, debug=True)