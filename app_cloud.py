"""E-Commerce Insight Analyzer - 클라우드 배포용 (headless Chromium)

Streamlit Community Cloud에서 동작하는 버전.
로컬 GUI 버전은 app.py 참조.

차이점:
- headless Chromium 사용 (Chrome 창이 열리지 않음)
- CAPTCHA 발생 시 안내 메시지 표시 후 중단
"""

import asyncio
import json
import streamlit as st

from utils.validators import validate_product_url, detect_platform, validate_api_key
from crawler.url_parser import parse_url
from crawler.browser_cloud import CoupangBrowserCloud, NaverBrowserCloud
from crawler.product_page import ProductPageScraper
from crawler.review_scraper import ReviewScraper
from crawler.qna_scraper import QnAScraper
from crawler.naver_product_page import NaverProductPageScraper
from crawler.naver_review_scraper import NaverReviewScraper
from crawler.naver_qna_scraper import NaverQnAScraper
from analyzer.ai_client import create_ai_client
from analyzer.story_analyzer import StoryAnalyzer
from analyzer.review_analyzer import ReviewAnalyzer
from analyzer.qna_analyzer import QnAAnalyzer
from analyzer.full_report import FullReportAnalyzer
from exporter.excel_exporter import ExcelExporter
from exporter.word_exporter import WordExporter

st.set_page_config(
    page_title="E-Commerce Insight Analyzer",
    page_icon="🔍",
    layout="wide",
)

st.markdown("""
<style>
    .main-title { font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem; }
    .sub-title { color: #666; font-size: 1rem; margin-bottom: 2rem; }
    .stButton > button[kind="primary"] { width: 100%; }
    .platform-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
        margin-left: 8px;
    }
    .badge-coupang { background: #FF6B35; color: white; }
    .badge-naver { background: #03C75A; color: white; }
    .cloud-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 8px;
        background: #6C63FF;
        color: white;
        font-size: 0.75rem;
        margin-left: 8px;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.markdown(
        '<div class="main-title">E-Commerce Insight Analyzer '
        '<span class="cloud-badge">Cloud</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sub-title">'
        '쿠팡 또는 네이버 스마트스토어 상품 링크를 입력하면 상세페이지, 리뷰, Q&A를 자동 분석합니다'
        '</div>',
        unsafe_allow_html=True,
    )

    # 클라우드 안내
    with st.expander("Cloud 버전 안내", expanded=False):
        st.info(
            "**Cloud 버전 제한사항:**\n"
            "- 봇 탐지(CAPTCHA)가 발생하면 해당 상품의 데이터 수집이 제한될 수 있습니다\n"
            "- CAPTCHA 없이 접속되는 상품은 정상적으로 분석됩니다\n\n"
            "**로컬 버전 (제한 없음):**\n"
            "- GitHub에서 코드를 다운로드하여 로컬에서 실행하면 CAPTCHA를 직접 풀 수 있습니다\n"
            "- `git clone` → `pip install -r requirements.txt` → `streamlit run app.py`"
        )

    url = st.text_input(
        "상품 URL",
        placeholder="쿠팡 또는 네이버 스마트스토어 URL을 입력하세요",
    )

    if url and url.strip():
        platform = detect_platform(url)
        if platform == "coupang":
            st.markdown(
                '<span class="platform-badge badge-coupang">쿠팡</span> 상품이 감지되었습니다.',
                unsafe_allow_html=True,
            )
        elif platform == "naver":
            st.markdown(
                '<span class="platform-badge badge-naver">네이버 스마트스토어</span> 상품이 감지되었습니다.',
                unsafe_allow_html=True,
            )
        else:
            st.warning("지원하지 않는 URL입니다. 쿠팡 또는 네이버 스마트스토어 URL을 입력해주세요.")

    st.subheader("AI 모델 선택")
    col1, col2 = st.columns(2)
    with col1:
        use_claude = st.checkbox("Anthropic Claude", value=True)
    with col2:
        use_openai = st.checkbox("OpenAI o4-mini", value=False)

    if use_claude:
        claude_key = st.text_input("Anthropic API Key", type="password")
    if use_openai:
        openai_key = st.text_input("OpenAI API Key", type="password")

    st.subheader("분석 옵션")
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        do_story = st.checkbox("상세페이지 스토리 분석", value=True)
    with col_b:
        do_review = st.checkbox("리뷰 분석", value=True)
    with col_c:
        do_qna = st.checkbox("상품문의 분석", value=True)
    with col_d:
        do_full = st.checkbox("전체 통합 분석", value=True)

    if st.button("분석 시작", type="primary"):
        url_valid, url_msg, platform = validate_product_url(url)
        if not url_valid:
            st.error(url_msg)
            return

        if not use_openai and not use_claude:
            st.error("최소 하나의 AI 모델을 선택해주세요.")
            return

        if use_claude:
            key_valid, key_msg = validate_api_key(claude_key, "claude")
            if not key_valid:
                st.error(f"Claude: {key_msg}")
                return

        if use_openai:
            key_valid, key_msg = validate_api_key(openai_key, "openai")
            if not key_valid:
                st.error(f"OpenAI: {key_msg}")
                return

        if not any([do_story, do_review, do_qna, do_full]):
            st.error("최소 하나의 분석 옵션을 선택해주세요.")
            return

        ai_configs = []
        if use_claude:
            ai_configs.append(("claude", claude_key, "Anthropic Claude"))
        if use_openai:
            ai_configs.append(("openai", openai_key, "OpenAI o4-mini"))

        run_analysis(url, platform, ai_configs, do_story, do_review, do_qna, do_full)

    st.divider()
    st.warning(
        "본 서비스는 모든 분석 기록을 저장하지 않습니다. "
        "결과는 반드시 다운로드 받으세요. "
        "페이지를 벗어나면 결과는 삭제됩니다."
    )


def run_analysis(url, platform, ai_configs, do_story, do_review, do_qna, do_full):
    """전체 분석 파이프라인 (클라우드 headless 모드)"""
    try:
        product_info = parse_url(url, platform)
    except ValueError as e:
        st.error(str(e))
        return

    progress = st.progress(0, text="준비 중...")
    status = st.empty()

    product_data = None
    reviews = []
    qna_pairs = []

    try:
        status.info("크롤링을 시작합니다...")
        progress.progress(5, text="브라우저 시작 중...")

        if platform == "coupang":
            crawl_fn = _make_coupang_crawl(
                product_info, do_story, do_review, do_qna, do_full, progress, status
            )
        else:
            crawl_fn = _make_naver_crawl(
                product_info, do_story, do_review, do_qna, do_full, progress, status
            )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(asyncio.run, crawl_fn()).result()
            else:
                result = loop.run_until_complete(crawl_fn())
        except RuntimeError:
            result = asyncio.run(crawl_fn())

        if result is None:
            return

        product_data, reviews, qna_pairs = result

        # AI 분석
        all_results = {}

        for idx, (provider, api_key, label) in enumerate(ai_configs):
            progress.progress(50, text=f"{label} 분석 시작...")
            ai_client = create_ai_client(provider, api_key)

            story_result = ""
            review_result = ""
            qna_result = ""
            full_result = ""

            if do_story and product_data:
                progress.progress(55, text=f"[{label}] 상세페이지 스토리 분석 중...")
                analyzer = StoryAnalyzer(ai_client)
                story_result = analyzer.analyze(product_data)

            if do_review and reviews:
                progress.progress(65, text=f"[{label}] 리뷰 분석 중...")
                analyzer = ReviewAnalyzer(ai_client)
                review_result = analyzer.analyze(reviews)

            if do_qna and qna_pairs:
                progress.progress(75, text=f"[{label}] Q&A 분석 중...")
                analyzer = QnAAnalyzer(ai_client)
                qna_result = analyzer.analyze(qna_pairs)

            if do_full and (story_result or review_result or qna_result):
                progress.progress(85, text=f"[{label}] 종합 리포트 생성 중...")
                analyzer = FullReportAnalyzer(ai_client)
                full_result = analyzer.analyze(
                    product_data, story_result, review_result, qna_result
                )

            all_results[label] = {
                "story": story_result,
                "review": review_result,
                "qna": qna_result,
                "full": full_result,
            }

        progress.progress(95, text="리포트 생성 중...")
        progress.progress(100, text="분석 완료!")
        status.success("모든 분석이 완료되었습니다!")

        for label, res in all_results.items():
            display_results(
                label, product_data, reviews, qna_pairs, res,
                do_story, do_review, do_qna, do_full,
            )
            create_downloads(
                label, platform, product_data, reviews, qna_pairs, res,
            )

    except Exception as e:
        st.error(f"분석 중 오류가 발생했습니다: {e}")
        progress.empty()


def _make_coupang_crawl(product_info, do_story, do_review, do_qna, do_full, progress, status):
    async def crawl():
        product_data = None
        reviews = []
        qna_pairs = []

        browser = CoupangBrowserCloud()
        try:
            await browser.launch()
            progress.progress(10, text="쿠팡 상품 페이지 접속 중...")

            success = await browser.navigate(product_info["full_url"])
            if not success:
                st.error(
                    "쿠팡 페이지 접속에 실패했습니다. (봇 차단)\n\n"
                    "쿠팡은 봇 탐지가 강력하여 Cloud 환경에서 차단될 수 있습니다.\n"
                    "로컬 버전(`streamlit run app.py`)을 사용해보세요."
                )
                return None

            if do_story or do_full:
                progress.progress(15, text="상품 정보 수집 중...")
                scraper = ProductPageScraper()
                product_data = await scraper.scrape(browser.page, product_info)

            if do_review or do_full:
                progress.progress(20, text="리뷰 수집 중...")
                review_scraper = ReviewScraper()
                reviews = await review_scraper.scrape_all(
                    browser, product_info,
                    lambda msg, pct: progress.progress(20 + int(pct * 0.25), text=msg),
                )
                status.success(_review_summary(reviews))

            if do_qna or do_full:
                progress.progress(45, text="Q&A 수집 중...")
                qna_scraper = QnAScraper()
                qna_pairs = await qna_scraper.scrape(
                    browser.page, lambda msg: status.info(msg),
                )
                status.success(_qna_summary(qna_pairs))

            return (product_data, reviews, qna_pairs)
        finally:
            await browser.close()

    return crawl


def _make_naver_crawl(product_info, do_story, do_review, do_qna, do_full, progress, status):
    async def crawl():
        product_data = None
        reviews = []
        qna_pairs = []

        browser = NaverBrowserCloud()
        try:
            await browser.launch()
            progress.progress(10, text="네이버 스마트스토어 접속 중...")
            browser.set_status_callback(lambda msg: status.info(msg))

            success = await browser.navigate_with_mobile_fallback(
                product_info["desktop_url"],
                product_info["mobile_url"],
            )

            # CAPTCHA 감지 시 안내 메시지
            if not success and browser.captcha_detected:
                st.warning(
                    "**봇 탐지(CAPTCHA)가 발생하여 데이터 수집이 제한되었습니다.**\n\n"
                    "네이버에서 자동 접속을 차단했습니다. 아래 방법을 시도해보세요:\n"
                    "- 잠시 후 다시 시도해주세요 (보통 몇 분 후 해제됩니다)\n"
                    "- 다른 상품 URL로 시도해보세요\n"
                    "- **로컬 버전**에서는 CAPTCHA를 직접 풀 수 있습니다: "
                    "`streamlit run app.py`"
                )
                return None

            if not success:
                st.error(
                    "네이버 스마트스토어 접속에 실패했습니다. "
                    "잠시 후 다시 시도하거나, 다른 상품 URL을 사용해보세요."
                )
                return None

            progress.progress(12, text="페이지 데이터 추출 중...")
            next_data = await browser.extract_page_data_json()
            if next_data:
                status.info("페이지 JSON 데이터 추출 성공!")
            else:
                status.info("JSON 데이터 없음 — DOM 기반으로 수집합니다")

            if do_story or do_full:
                progress.progress(15, text="상품 정보 수집 중...")
                scraper = NaverProductPageScraper()
                product_data = await scraper.scrape(browser.page, product_info, next_data)

            if do_review or do_full:
                progress.progress(20, text="리뷰 수집 중...")
                review_scraper = NaverReviewScraper()
                reviews = await review_scraper.scrape_all(
                    browser, product_info, next_data,
                    lambda msg, pct: progress.progress(20 + int(pct * 0.25), text=msg),
                )
                status.success(_review_summary(reviews))

            if do_qna or do_full:
                progress.progress(45, text="Q&A 수집 중...")
                qna_scraper = NaverQnAScraper()
                qna_pairs = await qna_scraper.scrape(
                    browser, product_info, next_data,
                    lambda msg: status.info(msg),
                )
                status.success(_qna_summary(qna_pairs))

            return (product_data, reviews, qna_pairs)
        finally:
            await browser.close()

    return crawl


def _review_summary(reviews: list) -> str:
    """리뷰 수집 결과 요약 문자열 생성."""
    if not reviews:
        return "리뷰 0건 수집"
    total = len(reviews)
    rating_counts = {}
    for r in reviews:
        score = r.get("rating")
        if score is not None:
            key = int(round(float(score)))
            rating_counts[key] = rating_counts.get(key, 0) + 1
    parts = [f"리뷰 {total}건 수집"]
    rating_strs = []
    for star in (5, 4, 3, 2, 1):
        cnt = rating_counts.get(star, 0)
        if cnt > 0:
            rating_strs.append(f"{star}점: {cnt}건")
    if rating_strs:
        parts.append(f"({' / '.join(rating_strs)})")
    return " ".join(parts)


def _qna_summary(qna_pairs: list) -> str:
    """Q&A 수집 결과 요약 문자열 생성."""
    if not qna_pairs:
        return "상품 문의 0건 수집"
    total = len(qna_pairs)
    secret = sum(
        1 for p in qna_pairs
        if "(비공개" in p.get("question", "") or "비밀글" in p.get("question", "")
    )
    answered = sum(
        1 for p in qna_pairs
        if p.get("answer", "") and p.get("answer", "") not in ("", "(답변완료)")
    )
    parts = [f"전체 상품 문의 {total}건"]
    if secret > 0:
        parts.append(f"비밀글 {secret}건")
    parts.append(f"확인답변 {answered}건")
    return ", ".join(parts)


def display_results(label, product_data, reviews, qna_pairs, res, do_story, do_review, do_qna, do_full):
    st.divider()
    st.subheader(f"분석 결과 - {label}")

    if do_story and res["story"]:
        with st.expander("상세페이지 스토리 분석", expanded=True):
            st.markdown(res["story"])

    if do_review and res["review"]:
        with st.expander("리뷰 분석", expanded=True):
            st.markdown(res["review"])
            if reviews:
                st.caption(_review_summary(reviews))

    if do_qna and res["qna"]:
        with st.expander("상품문의(Q&A) 분석", expanded=True):
            st.markdown(res["qna"])
            if qna_pairs:
                st.caption(_qna_summary(qna_pairs))

    if do_full and res["full"]:
        with st.expander("종합 리포트", expanded=True):
            st.markdown(res["full"])


def create_downloads(label, platform, product_data, reviews, qna_pairs, res):
    st.divider()
    st.subheader(f"다운로드 - {label}")

    safe_label = label.replace(" ", "_").lower()
    prefix = f"{platform}_analysis"
    col1, col2, col3 = st.columns(3)

    with col1:
        try:
            exporter = ExcelExporter()
            excel_bytes = exporter.generate(
                product_data, reviews, qna_pairs,
                res["story"], res["review"], res["qna"], res["full"],
            )
            st.download_button(
                label="Excel (.xlsx)", data=excel_bytes,
                file_name=f"{prefix}_{safe_label}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"excel_{safe_label}",
            )
        except Exception as e:
            st.error(f"Excel 생성 실패: {e}")

    with col2:
        try:
            exporter = WordExporter()
            word_bytes = exporter.generate(
                product_data, res["story"], res["review"], res["qna"], res["full"],
            )
            st.download_button(
                label="Word (.docx)", data=word_bytes,
                file_name=f"{prefix}_{safe_label}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"word_{safe_label}",
            )
        except Exception as e:
            st.error(f"Word 생성 실패: {e}")

    with col3:
        raw_data = {
            "platform": platform, "reviews": reviews,
            "qna": qna_pairs, "product": product_data, "analysis": res,
        }
        st.download_button(
            label="원본 데이터 (.json)",
            data=json.dumps(raw_data, ensure_ascii=False, indent=2),
            file_name=f"{prefix}_raw_{safe_label}.json",
            mime="application/json", key=f"json_{safe_label}",
        )


if __name__ == "__main__":
    main()
