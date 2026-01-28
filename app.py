import streamlit as st
import pandas as pd
import time
import json
import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from io import BytesIO
import concurrent.futures
import threading

# ============================================
# 页面配置
# ============================================
st.set_page_config(
    page_title="印尼电商评论爬取工具",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式
st.markdown("""
<style>
    .main-title {
        text-align: center;
        color: #1E3A8A;
        font-size: 2.5rem;
        margin-bottom: 2rem;
    }
    .section-header {
        background-color: #3B82F6;
        color: white;
        padding: 12px;
        border-radius: 8px;
        margin: 20px 0;
        font-size: 1.3rem;
    }
    .success-box {
        background-color: #D1FAE5;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #10B981;
        margin: 10px 0;
    }
    .warning-box {
        background-color: #FEF3C7;
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid #F59E0B;
        margin: 10px 0;
    }
    .code-box {
        background-color: #1E293B;
        color: #E2E8F0;
        padding: 15px;
        border-radius: 8px;
        font-family: 'Courier New', monospace;
        overflow-x: auto;
    }
</style>
""", unsafe_allow_html=True)

# 应用标题
st.markdown('<h1 class="main-title">🛒 印尼电商与社交媒体评论爬取工具</h1>', unsafe_allow_html=True)

# 初始化session state
if 'tt_product_comments' not in st.session_state:
    st.session_state.tt_product_comments = []
if 'shopee_comments' not in st.session_state:
    st.session_state.shopee_comments = []
if 'tt_video_comments' not in st.session_state:
    st.session_state.tt_video_comments = []
if 'crawler_status' not in st.session_state:
    st.session_state.crawler_status = {}

# ============================================
# 侧边栏配置
# ============================================
with st.sidebar:
    st.title("⚙️ 配置选项")
    
    st.markdown("### 🕷️ 爬虫设置")
    
    # 爬取数量设置
    max_comments = st.slider("最大评论爬取数量", 10, 1000, 100, 10)
    
    # 线程设置
    use_multithreading = st.checkbox("启用多线程爬取", value=True)
    if use_multithreading:
        thread_count = st.slider("线程数量", 1, 10, 3)
    
    # 代理设置
    use_proxy = st.checkbox("使用代理服务器", value=False)
    if use_proxy:
        proxy_list = st.text_area("代理服务器列表（每行一个）", 
                                 placeholder="http://proxy1:port\nhttp://proxy2:port")
    
    st.markdown("---")
    
    st.markdown("### 📊 数据保存")
    
    # 数据格式
    output_format = st.radio("输出格式", ["Excel", "CSV", "JSON"])
    
    # 自动保存
    auto_save = st.checkbox("自动保存数据", value=True)
    
    st.markdown("---")
    
    st.markdown("### 🆘 帮助")
    
    with st.expander("使用教程"):
        st.markdown("""
        1. **TikTok产品评论**: 输入TikTok Shop产品URL
        2. **Shopee产品评论**: 输入Shopee印尼站产品URL
        3. **TikTok视频评论**: 输入TikTok视频URL或视频ID
        
        **注意**: 
        - 请确保网络稳定
        - 大量爬取时请使用代理
        - 遵守网站robots.txt规定
        """)
    
    with st.expander("URL格式示例"):
        st.markdown("""
        **TikTok Shop产品**: 
        ```
        https://www.tiktok.com/@username/video/123456789
        https://www.tiktok.com/t/ZT12345678/
        ```
        
        **Shopee印尼产品**:
        ```
        https://shopee.co.id/product-name-i.123456789.9876543210
        ```
        
        **TikTok视频**:
        ```
        https://www.tiktok.com/@username/video/1234567890123456789
        https://vm.tiktok.com/ZM12345678/
        ```
        """)

# ============================================
# TikTok产品评论爬取模块
# ============================================
st.markdown('<div class="section-header">1. TikTok印尼产品评论爬取</div>', unsafe_allow_html=True)

# 创建选项卡
tab1, tab2, tab3 = st.tabs(["单产品爬取", "批量爬取", "高级设置"])

with tab1:
    st.markdown("### 🛍️ 单产品评论爬取")
    
    # URL输入
    tt_product_url = st.text_input(
        "输入TikTok产品URL",
        placeholder="例如: https://www.tiktok.com/@toko_anda/video/123456789",
        key="tt_product_url"
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # 爬取选项
        include_ratings = st.checkbox("包含评分", value=True)
    
    with col2:
        include_images = st.checkbox("包含图片", value=False)
    
    with col3:
        include_replies = st.checkbox("包含回复", value=True)
    
    if st.button("🚀 开始爬取TikTok产品评论", type="primary", use_container_width=True):
        if not tt_product_url:
            st.error("请输入TikTok产品URL")
        else:
            with st.spinner("正在初始化爬虫..."):
                # 清空之前的数据
                st.session_state.tt_product_comments = []
                
                # 创建状态指示器
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                try:
                    # 初始化Chrome选项
                    chrome_options = Options()
                    chrome_options.add_argument("--headless")  # 无头模式
                    chrome_options.add_argument("--no-sandbox")
                    chrome_options.add_argument("--disable-dev-shm-usage")
                    chrome_options.add_argument("--disable-gpu")
                    chrome_options.add_argument("--window-size=1920,1080")
                    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
                    
                    # 使用undetected-chromedriver避免被检测
                    driver = uc.Chrome(options=chrome_options)
                    
                    status_text.text("正在访问TikTok页面...")
                    driver.get(tt_product_url)
                    
                    # 等待页面加载
                    time.sleep(5)
                    
                    # 尝试获取视频ID
                    video_id_match = re.search(r'video/(\d+)', tt_product_url)
                    video_id = video_id_match.group(1) if video_id_match else "unknown"
                    
                    # 模拟滚动以加载评论
                    status_text.text("正在加载评论...")
                    
                    # 获取初始评论
                    comments_loaded = 0
                    max_scrolls = 20  # 最大滚动次数
                    
                    for scroll in range(max_scrolls):
                        # 执行JavaScript滚动
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(2)
                        
                        # 提取评论
                        try:
                            # 尝试不同的评论选择器
                            comment_selectors = [
                                "div[data-e2e='comment-list'] div.css-1soki6-DivCommentItemContainer",
                                "div[class*='CommentItem']",
                                "div.comment-item",
                                "div[data-e2e='comment-item']"
                            ]
                            
                            for selector in comment_selectors:
                                comments = driver.find_elements(By.CSS_SELECTOR, selector)
                                if comments:
                                    break
                            
                            new_comments = len(comments) - comments_loaded
                            if new_comments > 0:
                                # 处理每个评论
                                for i in range(comments_loaded, len(comments)):
                                    try:
                                        comment_element = comments[i]
                                        
                                        # 获取评论信息
                                        comment_data = {
                                            'video_id': video_id,
                                            'crawl_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                            'platform': 'TikTok Shop'
                                        }
                                        
                                        # 尝试获取用户名
                                        try:
                                            username_elem = comment_element.find_element(By.CSS_SELECTOR, "a[href*='/@'], span[class*='username']")
                                            comment_data['username'] = username_elem.text.strip()
                                        except:
                                            comment_data['username'] = "Unknown"
                                        
                                        # 尝试获取评论内容
                                        try:
                                            content_elem = comment_element.find_element(By.CSS_SELECTOR, "div[class*='content'], p, span[class*='text']")
                                            comment_data['comment'] = content_elem.text.strip()
                                        except:
                                            comment_data['comment'] = ""
                                        
                                        # 尝试获取点赞数
                                        if include_ratings:
                                            try:
                                                likes_elem = comment_element.find_element(By.CSS_SELECTOR, "span[class*='like'], button[class*='like']")
                                                comment_data['likes'] = likes_elem.text.strip()
                                            except:
                                                comment_data['likes'] = "0"
                                        
                                        # 尝试获取时间
                                        try:
                                            time_elem = comment_element.find_element(By.CSS_SELECTOR, "span[class*='time'], time")
                                            comment_data['timestamp'] = time_elem.text.strip()
                                        except:
                                            comment_data['timestamp'] = ""
                                        
                                        # 尝试获取回复
                                        if include_replies:
                                            try:
                                                reply_elem = comment_element.find_element(By.CSS_SELECTOR, "div[class*='reply'], button[class*='reply']")
                                                comment_data['reply_count'] = reply_elem.text.strip()
                                            except:
                                                comment_data['reply_count'] = "0"
                                        
                                        st.session_state.tt_product_comments.append(comment_data)
                                        
                                    except Exception as e:
                                        st.warning(f"处理评论时出错: {str(e)}")
                                        continue
                                
                                comments_loaded = len(comments)
                                st.session_state.crawler_status['tt_product'] = f"已加载 {comments_loaded} 条评论"
                                
                                # 更新进度
                                progress = min((scroll + 1) / max_scrolls, 1.0)
                                progress_bar.progress(progress)
                                status_text.text(f"已加载 {comments_loaded} 条评论...")
                                
                        except Exception as e:
                            st.warning(f"提取评论时出错: {str(e)}")
                        
                        # 如果达到最大数量，停止
                        if comments_loaded >= max_comments:
                            break
                    
                    driver.quit()
                    
                    # 显示结果
                    if st.session_state.tt_product_comments:
                        st.success(f"✅ 成功爬取 {len(st.session_state.tt_product_comments)} 条评论")
                        
                        # 创建DataFrame
                        df_tt_product = pd.DataFrame(st.session_state.tt_product_comments)
                        
                        # 显示数据
                        st.dataframe(df_tt_product, use_container_width=True)
                        
                        # 下载按钮
                        output = BytesIO()
                        if output_format == "Excel":
                            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                df_tt_product.to_excel(writer, index=False, sheet_name='TikTok产品评论')
                            mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            file_name = f"tiktok_product_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        elif output_format == "CSV":
                            output.write(df_tt_product.to_csv(index=False).encode('utf-8'))
                            mime_type = "text/csv"
                            file_name = f"tiktok_product_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                        else:  # JSON
                            output.write(df_tt_product.to_json(orient='records', indent=2).encode('utf-8'))
                            mime_type = "application/json"
                            file_name = f"tiktok_product_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                        
                        st.download_button(
                            label="📥 下载评论数据",
                            data=output.getvalue(),
                            file_name=file_name,
                            mime=mime_type,
                            use_container_width=True
                        )
                    else:
                        st.warning("⚠️ 未找到评论数据")
                
                except Exception as e:
                    st.error(f"❌ 爬取失败: {str(e)}")
                    st.code(f"错误详情: {e}")

with tab2:
    st.markdown("### 📋 批量产品评论爬取")
    
    # 批量URL输入
    tt_urls_text = st.text_area(
        "输入多个TikTok产品URL（每行一个）",
        placeholder="https://www.tiktok.com/@shop1/video/123\nhttps://www.tiktok.com/@shop2/video/456",
        height=150
    )
    
    if st.button("🚀 批量爬取TikTok产品评论", type="primary", use_container_width=True):
        if not tt_urls_text.strip():
            st.error("请输入至少一个URL")
        else:
            urls = [url.strip() for url in tt_urls_text.split('\n') if url.strip()]
            st.info(f"准备爬取 {len(urls)} 个产品的评论...")

with tab3:
    st.markdown("### ⚙️ TikTok爬取高级设置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**爬取策略**")
        wait_time = st.slider("页面等待时间(秒)", 1, 10, 3)
        scroll_pause = st.slider("滚动间隔时间(秒)", 1, 5, 2)
        retry_count = st.slider("重试次数", 0, 5, 2)
    
    with col2:
        st.markdown("**数据过滤**")
        min_words = st.number_input("最少字数", 0, 100, 3)
        exclude_keywords = st.text_input("排除关键词（逗号分隔）", placeholder="spam,广告,推广")
    
    st.markdown("**Cookies设置**")
    cookies_json = st.text_area("Cookies JSON", placeholder='{"tt_chain_token": "your_token", ...}', height=100)

# ============================================
# Shopee印尼产品评论爬取模块
# ============================================
st.markdown('<div class="section-header">2. Shopee印尼产品评论爬取</div>', unsafe_allow_html=True)

shopee_tab1, shopee_tab2 = st.tabs(["单产品爬取", "产品ID批量爬取"])

with shopee_tab1:
    st.markdown("### 🛍️ Shopee单产品评论爬取")
    
    shopee_url = st.text_input(
        "输入Shopee印尼产品URL",
        placeholder="例如: https://shopee.co.id/Product-Name-i.123456789.9876543210",
        key="shopee_url"
    )
    
    col1, col2 = st.columns(2)
    
    with col1:
        shopee_rating_filter = st.selectbox(
            "评分过滤",
            ["全部", "5星", "4星", "3星", "2星", "1星"]
        )
    
    with col2:
        shopee_sort_by = st.selectbox(
            "排序方式",
            ["最新", "最相关", "最有帮助"]
        )
    
    if st.button("🚀 开始爬取Shopee评论", type="primary", use_container_width=True):
        if not shopee_url:
            st.error("请输入Shopee产品URL")
        else:
            with st.spinner("正在解析Shopee产品信息..."):
                try:
                    # 从URL提取shopid和itemid
                    shopid_match = re.search(r'i\.(\d+)\.(\d+)', shopee_url)
                    if shopid_match:
                        shopid = shopid_match.group(1)
                        itemid = shopid_match.group(2)
                        
                        st.success(f"✅ 解析成功: ShopID={shopid}, ItemID={itemid}")
                        
                        # 使用Shopee API获取评论
                        base_url = "https://shopee.co.id/api/v2/item/get_ratings"
                        
                        comments = []
                        offset = 0
                        limit = 50
                        
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        while len(comments) < max_comments:
                            # 构建API参数
                            params = {
                                'itemid': itemid,
                                'shopid': shopid,
                                'limit': limit,
                                'offset': offset,
                                'filter': 0 if shopee_rating_filter == "全部" else int(shopee_rating_filter[0]),
                                'flag': 1,
                                'type': 0
                            }
                            
                            # 添加请求头
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                'Accept': 'application/json',
                                'Accept-Language': 'id-ID,id;q=0.9,en;q=0.8',
                                'Referer': shopee_url
                            }
                            
                            # 发送请求
                            response = requests.get(base_url, params=params, headers=headers)
                            
                            if response.status_code == 200:
                                data = response.json()
                                
                                if data.get('data') and data['data'].get('ratings'):
                                    ratings = data['data']['ratings']
                                    
                                    for rating in ratings:
                                        comment_data = {
                                            'product_id': itemid,
                                            'shop_id': shopid,
                                            'crawl_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                            'platform': 'Shopee Indonesia',
                                            'username': rating.get('author_username', ''),
                                            'rating': rating.get('rating_star', 0),
                                            'comment': rating.get('comment', ''),
                                            'likes': rating.get('like_count', 0),
                                            'timestamp': datetime.fromtimestamp(rating.get('ctime', 0)).strftime('%Y-%m-%d %H:%M:%S'),
                                            'item_name': rating.get('product_items', [{}])[0].get('name', '') if rating.get('product_items') else '',
                                            'variation': rating.get('product_items', [{}])[0].get('model_name', '') if rating.get('product_items') else ''
                                        }
                                        
                                        # 处理图片
                                        if rating.get('images'):
                                            comment_data['images'] = ','.join(rating['images'])
                                        
                                        comments.append(comment_data)
                                    
                                    st.session_state.shopee_comments = comments
                                    status_text.text(f"已加载 {len(comments)} 条评论...")
                                    progress_bar.progress(min(len(comments) / max_comments, 1.0))
                                    
                                    # 如果没有更多评论或达到限制，停止
                                    if len(ratings) < limit or len(comments) >= max_comments:
                                        break
                                    
                                    offset += limit
                                    time.sleep(1)  # 避免请求过快
                                
                                else:
                                    st.warning("未找到更多评论数据")
                                    break
                            else:
                                st.error(f"API请求失败: {response.status_code}")
                                break
                        
                        # 显示结果
                        if st.session_state.shopee_comments:
                            st.success(f"✅ 成功爬取 {len(st.session_state.shopee_comments)} 条Shopee评论")
                            
                            # 创建DataFrame
                            df_shopee = pd.DataFrame(st.session_state.shopee_comments)
                            
                            # 显示数据
                            st.dataframe(df_shopee, use_container_width=True)
                            
                            # 显示统计信息
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                avg_rating = df_shopee['rating'].mean()
                                st.metric("平均评分", f"{avg_rating:.1f} ⭐")
                            
                            with col2:
                                total_likes = df_shopee['likes'].sum()
                                st.metric("总点赞数", total_likes)
                            
                            with col3:
                                with_images = df_shopee['images'].notna().sum() if 'images' in df_shopee.columns else 0
                                st.metric("带图评论", with_images)
                            
                            # 下载按钮
                            output = BytesIO()
                            if output_format == "Excel":
                                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                                    df_shopee.to_excel(writer, index=False, sheet_name='Shopee评论')
                                mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                file_name = f"shopee_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                            elif output_format == "CSV":
                                output.write(df_shopee.to_csv(index=False).encode('utf-8'))
                                mime_type = "text/csv"
                                file_name = f"shopee_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                            else:  # JSON
                                output.write(df_shopee.to_json(orient='records', indent=2).encode('utf-8'))
                                mime_type = "application/json"
                                file_name = f"shopee_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                            
                            st.download_button(
                                label="📥 下载Shopee评论数据",
                                data=output.getvalue(),
                                file_name=file_name,
                                mime=mime_type,
                                use_container_width=True
                            )
                        else:
                            st.warning("⚠️ 未找到评论数据")
                    
                    else:
                        st.error("❌ 无法从URL解析产品ID")
                
                except Exception as e:
                    st.error(f"❌ 爬取失败: {str(e)}")
                    st.code(f"错误详情: {e}")

with shopee_tab2:
    st.markdown("### 📋 通过产品ID批量爬取")
    
    shopee_ids_text = st.text_area(
        "输入多个产品ID（格式: shopid,itemid，每行一对）",
        placeholder="123456789,9876543210\n234567890,8765432109",
        height=150
    )
    
    if st.button("🚀 批量爬取Shopee产品", type="primary", use_container_width=True):
        if not shopee_ids_text.strip():
            st.error("请输入至少一个产品ID")
        else:
            ids = [line.strip() for line in shopee_ids_text.split('\n') if line.strip()]
            st.info(f"准备爬取 {len(ids)} 个产品的评论...")

# ============================================
# TikTok热门视频评论爬取模块
# ============================================
st.markdown('<div class="section-header">3. TikTok印尼热门视频评论爬取</div>', unsafe_allow_html=True)

tt_video_tab1, tt_video_tab2 = st.tabs(["单视频爬取", "热门话题爬取"])

with tt_video_tab1:
    st.markdown("### 🎬 TikTok单视频评论爬取")
    
    # 输入选项
    input_option = st.radio("输入方式", ["视频URL", "视频ID", "关键词搜索"], horizontal=True)
    
    if input_option == "视频URL":
        tt_video_url = st.text_input(
            "输入TikTok视频URL",
            placeholder="例如: https://www.tiktok.com/@username/video/1234567890123456789",
            key="tt_video_url"
        )
    elif input_option == "视频ID":
        video_id_input = st.text_input("输入视频ID", placeholder="1234567890123456789")
    else:  # 关键词搜索
        search_keyword = st.text_input("搜索关键词", placeholder="例如: produk indonesia, review")
        search_limit = st.slider("搜索视频数量", 1, 50, 10)
    
    col1, col2 = st.columns(2)
    
    with col1:
        include_user_info = st.checkbox("包含用户信息", value=True)
    
    with col2:
        translate_comments = st.checkbox("翻译为英文", value=False)
    
    if st.button("🚀 开始爬取TikTok视频评论", type="primary", use_container_width=True):
        st.warning("⚠️ TikTok视频评论爬取需要高级API密钥或模拟登录")
        st.info("""
        由于TikTok的反爬虫机制严格，需要以下任一种方式：
        
        1. **TikTok官方API**（需要申请）
        2. **第三方TikTok API服务**
        3. **模拟浏览器+账号登录**
        
        **替代方案**: 使用以下Python库（需要在本地环境安装）：
        ```
        pip install TikTokApi playwright
        playwrigh install chromium
        ```
        
        由于Streamlit Cloud环境限制，建议在本地运行此功能。
        """)
        
        # 显示模拟数据（用于演示）
        st.markdown("### 📊 示例数据（演示用）")
        
        # 创建示例数据
        example_comments = [
            {
                'video_id': '1234567890123456789',
                'username': 'user_indonesia1',
                'comment': 'Produknya bagus banget! 👍',
                'likes': 45,
                'timestamp': '2小时前',
                'user_followers': '1.2k',
                'location': 'Jakarta'
            },
            {
                'video_id': '1234567890123456789',
                'username': 'reviewer_id',
                'comment': 'Harga terjangkau, kualitas oke',
                'likes': 89,
                'timestamp': '5小时前',
                'user_followers': '5.7k',
                'location': 'Surabaya'
            },
            {
                'video_id': '1234567890123456789',
                'username': 'shop_lover',
                'comment': 'Mau coba juga nih, ada diskon ga?',
                'likes': 23,
                'timestamp': '1天前',
                'user_followers': '890',
                'location': 'Bandung'
            }
        ]
        
        df_example = pd.DataFrame(example_comments)
        st.dataframe(df_example, use_container_width=True)
        
        st.markdown("""
        **实际实现需要**: 
        1. 安装TikTokApi: `pip install TikTokApi`
        2. 安装浏览器驱动
        3. 处理验证码和登录
        """)

with tt_video_tab2:
    st.markdown("### 🔥 TikTok热门话题爬取")
    
    # 热门话题选择
    trending_topics = [
        "TikTok Shop Indonesia",
        "Produk Lokal",
        "UMKM Indonesia",
        "Fashion Indonesia",
        "Beauty Indonesia",
        "Kuliner Indonesia"
    ]
    
    selected_topics = st.multiselect("选择热门话题", trending_topics, default=["TikTok Shop Indonesia"])
    
    videos_per_topic = st.slider("每个话题爬取视频数", 1, 20, 5)
    
    if st.button("🚀 爬取热门话题评论", type="primary", use_container_width=True):
        st.info("此功能需要TikTok搜索API或模拟搜索")
        
        # 显示建议的实现代码
        st.markdown("### 💻 实现代码示例")
        
        code_example = """
        # TikTok视频评论爬取示例代码
        from TikTokApi import TikTokApi
        import asyncio
        
        async def get_video_comments(video_id):
            async with TikTokApi() as api:
                await api.create_sessions(ms_tokens=['your_token'], num_sessions=1, sleep_after=3)
                
                video = api.video(id=video_id)
                video_info = await video.info()
                
                comments = []
                async for comment in video.comments(count=100):
                    comments.append({
                        'username': comment.user.username,
                        'comment': comment.text,
                        'likes': comment.diggCount,
                        'timestamp': comment.createTime
                    })
                
                return comments
        
        # 使用
        comments = asyncio.run(get_video_comments('1234567890123456789'))
        """
        
        st.code(code_example, language='python')

# ============================================
# 数据管理与导出
# ============================================
st.markdown('<div class="section-header">📊 数据管理与导出</div>', unsafe_allow_html=True)

data_tabs = st.tabs(["数据合并", "数据分析", "导出设置"])

with data_tabs[0]:
    st.markdown("### 🔗 合并所有爬取的数据")
    
    # 选择要合并的数据集
    datasets_to_merge = st.multiselect(
        "选择要合并的数据集",
        ["TikTok产品评论", "Shopee评论", "TikTok视频评论"],
        default=["TikTok产品评论", "Shopee评论"]
    )
    
    if st.button("合并数据", use_container_width=True):
        all_data = []
        
        if "TikTok产品评论" in datasets_to_merge and st.session_state.tt_product_comments:
            all_data.extend(st.session_state.tt_product_comments)
        
        if "Shopee评论" in datasets_to_merge and st.session_state.shopee_comments:
            all_data.extend(st.session_state.shopee_comments)
        
        if "TikTok视频评论" in datasets_to_merge and st.session_state.tt_video_comments:
            all_data.extend(st.session_state.tt_video_comments)
        
        if all_data:
            df_merged = pd.DataFrame(all_data)
            st.success(f"✅ 合并成功！共 {len(all_data)} 条记录")
            st.dataframe(df_merged.head(20), use_container_width=True)
            
            # 导出合并数据
            output = BytesIO()
            if output_format == "Excel":
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df_merged.to_excel(writer, index=False, sheet_name='合并评论数据')
                mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                file_name = f"merged_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            elif output_format == "CSV":
                output.write(df_merged.to_csv(index=False).encode('utf-8'))
                mime_type = "text/csv"
                file_name = f"merged_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            else:  # JSON
                output.write(df_merged.to_json(orient='records', indent=2).encode('utf-8'))
                mime_type = "application/json"
                file_name = f"merged_comments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            
            st.download_button(
                label="📥 下载合并数据",
                data=output.getvalue(),
                file_name=file_name,
                mime=mime_type,
                use_container_width=True
            )
        else:
            st.warning("没有可合并的数据")

with data_tabs[1]:
    st.markdown("### 📈 数据分析")
    
    if st.session_state.shopee_comments:
        df_shopee = pd.DataFrame(st.session_state.shopee_comments)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 评分分布
            st.markdown("**评分分布**")
            rating_counts = df_shopee['rating'].value_counts().sort_index()
            for rating, count in rating_counts.items():
                st.write(f"{'⭐' * int(rating)}: {count} 条")
        
        with col2:
            # 词云生成（模拟）
            st.markdown("**热门关键词**")
            from collections import Counter
            import re
            
            all_comments = ' '.join(df_shopee['comment'].dropna().astype(str))
            words = re.findall(r'\b\w{3,}\b', all_comments.lower())
            word_counts = Counter(words).most_common(10)
            
            for word, count in word_counts:
                st.write(f"{word}: {count}")
        
        with col3:
            # 时间分布
            st.markdown("**评论时间分布**")
            if 'timestamp' in df_shopee.columns:
                df_shopee['date'] = pd.to_datetime(df_shopee['timestamp']).dt.date
                daily_counts = df_shopee['date'].value_counts().sort_index().tail(7)
                for date, count in daily_counts.items():
                    st.write(f"{date}: {count} 条")

with data_tabs[2]:
    st.markdown("### ⚙️ 导出设置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**导出选项**")
        include_metadata = st.checkbox("包含元数据", value=True)
        compress_data = st.checkbox("压缩数据", value=False)
        split_large_files = st.checkbox("分割大文件", value=False)
        
        if split_large_files:
            split_size = st.number_input("每个文件最大行数", 1000, 10000, 5000)
    
    with col2:
        st.markdown("**字段选择**")
        default_fields = ['username', 'comment', 'rating', 'timestamp', 'platform']
        selected_fields = st.multiselect("选择导出的字段", default_fields, default=default_fields)
    
    st.markdown("**自动导出设置**")
    auto_export_interval = st.selectbox(
        "自动导出间隔",
        ["不自动导出", "每小时", "每天", "每次爬取后"]
    )

# ============================================
# 页脚
# ============================================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>印尼电商与社交媒体评论爬取工具 | 遵守robots.txt和网站使用条款</p>
    <p>仅供学习和研究使用 | 请勿用于商业用途或违反服务条款</p>
</div>
""", unsafe_allow_html=True)

# ============================================
# 部署说明
# ============================================
with st.expander("📋 部署说明"):
    st.markdown("""
    ## 🚀 Streamlit Cloud 部署步骤
    
    ### 1. 创建GitHub仓库
    ```
    1. 登录GitHub (github.com)
    2. 点击右上角 + → New repository
    3. 仓库名: indonesia-comment-crawler
    4. 选择 Public
    5. 勾选 Add a README file
    6. 点击 Create repository
    ```
    
    ### 2. 上传代码文件
    ```
    1. 在仓库页面点击 Add file → Create new file
    2. 文件名: app.py
    3. 复制上面的完整代码到文件
    4. 点击 Commit changes
    5. 创建 requirements.txt 文件，内容如下：
    ```
    
    st.code("""
streamlit>=1.28.0
pandas>=2.0.0
requests>=2.31.0
beautifulsoup4>=4.12.0
selenium>=4.15.0
undetected-chromedriver>=3.5.0
lxml>=4.9.0
""", language='text')
    
    st.markdown("""
    ### 3. 部署到Streamlit Cloud
    ```
    1. 访问 https://share.streamlit.io/
    2. 用GitHub账号登录
    3. 点击 New app
    4. 选择你的仓库和分支
    5. Main file path: app.py
    6. 点击 Deploy!
    ```
    
    ### 4. 本地运行（替代方案）
    ```
    1. 安装Python 3.8+
    2. pip install -r requirements.txt
    3. streamlit run app.py
    ```
    
    ## ⚠️ 重要注意事项
    
    ### TikTok爬取限制
    由于TikTok的反爬虫机制严格，在Streamlit Cloud上可能无法直接运行。
    解决方案：
    1. 使用本地环境运行TikTok爬取部分
    2. 申请TikTok官方API
    3. 使用第三方TikTok数据服务
    
    ### Shopee爬取说明
    Shopee API相对稳定，但需要注意：
    1. 请求频率不要过高（建议1秒/次）
    2. 遵守robots.txt
    3. 仅用于学习研究
    
    ### 法律合规
    1. 遵守印尼当地法律
    2. 尊重用户隐私
    3. 不用于商业竞争
    4. 注明数据来源
    """)
