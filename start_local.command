#!/bin/bash
# E-Commerce Insight Analyzer - 로컬 서버 시작
cd "$(dirname "$0")"
echo "🏪 E-Commerce Insight Analyzer 시작 중..."
echo ""
echo "브라우저에서 http://localhost:8501 이 열립니다."
echo "종료하려면 이 창에서 Ctrl+C를 누르세요."
echo ""
open http://localhost:8501
streamlit run app.py
