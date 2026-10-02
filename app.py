import streamlit as st

from translator import (
    LANGUAGES,
    MAX_CHARS,
    TONES,
    MissingAPIKeyError,
    ModelNotFoundError,
    TranslationError,
    translate,
)

FLAGS = {"영어": "🇺🇸", "일본어": "🇯🇵", "베트남어": "🇻🇳"}
WARN_CHARS = 4500

st.set_page_config(page_title="다국어 번역기", page_icon="🌐", layout="centered")

st.markdown(
    """
    <style>
    h1, .app-subtitle { word-break: keep-all; }
    .app-subtitle { opacity: 0.7; margin-top: -0.75rem; margin-bottom: 1.5rem; }
    .char-count { text-align: right; font-size: 0.85rem; opacity: 0.7; margin-top: -0.5rem; }
    .char-count.warn { color: #f08c00; opacity: 1; }
    .char-count.over { color: #e03131; opacity: 1; font-weight: 600; }
    [data-testid="stTabs"] [data-testid="stCode"] { margin-top: 0.5rem; }
    textarea, [data-testid="stCode"] pre { overflow-wrap: anywhere; }
    </style>
    """,
    unsafe_allow_html=True,
)


def clear_input():
    st.session_state["text"] = ""
    st.session_state.pop("results", None)


with st.sidebar:
    st.header("설정")
    selected = st.multiselect("번역 언어", list(LANGUAGES), default=list(LANGUAGES))
    tone = st.radio("번역 톤", list(TONES), horizontal=True)
    st.divider()
    st.markdown(
        """
        **사용법**
        1. 번역할 글을 입력합니다.
        2. 번역 언어와 톤을 고릅니다.
        3. **번역하기**를 누릅니다.

        원문 언어는 자동으로 인식합니다.
        """
    )

st.title("🌐 다국어 번역기")
st.markdown('<p class="app-subtitle">영어 · 일본어 · 베트남어로 한 번에 번역</p>', unsafe_allow_html=True)

text = st.text_area(
    "번역할 내용을 입력하세요",
    key="text",
    height=200,
    placeholder="예) 안녕하세요, 만나서 반갑습니다.",
)

count_class = "over" if len(text) > MAX_CHARS else "warn" if len(text) >= WARN_CHARS else ""
st.markdown(
    f'<p class="char-count {count_class}">{len(text):,} / {MAX_CHARS:,}자</p>',
    unsafe_allow_html=True,
)

col_translate, col_clear = st.columns([4, 1])
translate_clicked = col_translate.button("번역하기", type="primary", width="stretch")
col_clear.button("지우기", on_click=clear_input, width="stretch")

if translate_clicked:
    # 실패한 요청 아래에 이전 결과가 남아 새 결과로 오해되지 않도록 먼저 비운다
    st.session_state.pop("results", None)
    if not text.strip():
        st.warning("번역할 내용을 입력해 주세요.")
    elif not selected:
        st.warning("번역할 언어를 하나 이상 선택해 주세요.")
    elif len(text) > MAX_CHARS:
        st.error(f"최대 {MAX_CHARS:,}자까지 입력할 수 있습니다.")
    else:
        try:
            with st.spinner("번역 중..."):
                results = translate(text, [LANGUAGES[name] for name in selected], tone)
            # 번역에 사용한 언어 순서대로 {표시 이름: 번역문} 저장
            st.session_state["results"] = {name: results[LANGUAGES[name]] for name in selected}
            st.toast("번역이 완료되었습니다.", icon="✅")
        except MissingAPIKeyError:
            st.error("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해 주세요.")
        except ModelNotFoundError as e:
            st.error(f"모델({e.model})을 찾을 수 없습니다. OPENAI_MODEL 값을 확인해 주세요.")
        except TranslationError:
            st.error("번역 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")

st.subheader("번역 결과")
results = st.session_state.get("results")
if results:
    tabs = st.tabs([f"{FLAGS[name]} {name}" for name in results])
    for tab, translated in zip(tabs, results.values()):
        with tab:
            st.code(translated, language=None, wrap_lines=True)

    download_text = "\n\n".join(f"[{name}]\n{translated}" for name, translated in results.items())
    st.download_button(
        "결과 다운로드 (.txt)",
        data=download_text,
        file_name="translation.txt",
        mime="text/plain",
        width="stretch",
    )
else:
    st.info("번역 결과가 여기에 표시됩니다.")
