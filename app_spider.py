
# ===== START: app_first_part.py =====

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt, polars as pl
from datetime import datetime, timedelta
from matplotlib.gridspec import GridSpec
import os, glob
import pymysql
from PIL import Image
from streamlit_scroll_to_top import scroll_to_here
from streamlit_extras.stylable_container import stylable_container
import time
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import re
import numpy as np
from pathlib import Path

from streamlit import runtime
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit_modal import Modal
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

import uuid
import sso_config
import pickle
import shutil

import hashlib
from hdfs import InsecureClient
from hdfs import HdfsError
from connectHdfs import get_active_namenode
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import paramiko
import traceback as tb
import subprocess
import shlex
import math

from streamlit_cookies_controller import CookieController
from io import BytesIO

# DB 정보 - 유출 방지 위해 config로 설정
with open('db_info.pkl', 'rb') as f:
    db_info = pickle.load(f)
DB_HOST = db_info["DB_HOST"]        # 없으면 KeyError (조기 오류)
DB_PORT = db_info["DB_PORT"]
DB_NAME = db_info["DB_NAME"]
DB_USER = db_info["DB_USER"]
DB_PASSWORD = db_info["DB_PASSWORD"]
HDFS_HOST = db_info["HDFS_HOST"]
HDFS_NAME = db_info["HDFS_NAME"]
HDFS_PASSWORD = db_info["HDFS_PASSWORD"]

st.set_page_config(layout="wide", page_title='ETCH Spider',page_icon='https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS3Kz2J3hZTWRESlhfC6h0Zk6WEbolVV2Cy9JLQb2-mK8oA14Qey80G_rfT9CklBMCVWjA&usqp=CAU')

def split_by_reverse(s: str):
    rev = s[::-1]
    a = "_T_"
    # "_T_" 뒤집은 문자열
    rev_t = a[::-1]   # "_T_" -> "_T_" (대칭이 아니라서 이렇게 써두는 게 안전)

    if rev_t not in rev:
        a = "_E_"
        rev_t = a[::-1]
        if rev_t not in rev:
            raise ValueError("_T_ and _E_ not found")

    left_rev, right_rev = rev.split(rev_t, 1)

    sensor = right_rev[::-1]+ a[:-1]
    step = left_rev[::-1]

    return sensor, step

class DummyController:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value

    def getAll(self):  # ✅ getAll() 메서드 추가
        return self.store

# controller는 가장 먼저 초기화되어야 함
controller = DummyController()

# session 초기화
if 'claim_value' not in st.session_state:
    st.session_state['claim_value'] = None

# cookie 초기화
if 'claim_value' not in controller.getAll():
    controller.set('claim_value', None)

# user 초기화
if 'user' not in st.session_state:
    st.session_state.user = None

def is_valid_date(s):
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return True
    except:
        return False

def sso(): # sso_config.py 의 정보를 통해 AD SSO 서버에 POST 요청하는 URL 생성
    nonce_val = uuid.uuid4().urn
    nonce_val = nonce_val[9:]
    idp_url = sso_config.IDP_Config['Idp.EntityID']
    auth_param = '?client_id=' + sso_config.IDP_Config['Idp.ClientID']
    auth_param += '&redirect_uri=' + sso_config.SP_Config['SP.RedirectUrl']
    auth_param += '&response_mode=form_post'
    auth_param += '&response_type=id_token'
    auth_param += '&scope=openid+profile'
    auth_param += '&nonce=' + nonce_val
    url = idp_url + auth_param
    # print(url)
    return url

# 자동 리디렉션 함수
def auto_redirect_to_login():
    login_url = sso()
    st.markdown(f"""
        <meta http-equiv="refresh" content="0;URL='{login_url}'" />
    """, unsafe_allow_html=True)

#============= 여기서부터 =============

def main():
    # st.title('SPIDER Login')

    # 1. 쿼리 파라미터 확인
    claim_value = st.query_params.to_dict()
    required_keys = {'unique_name', 'loginid', 'mail', 'deptname', 'grdname', 'username'}

    # 2. 쿼리파라미터가 유효하면 session_state와 controller에 저장
    if set(claim_value.keys()) == required_keys:
        st.session_state['claim_value'] = claim_value
        if controller.get('claim_value') is None:
            controller.set('claim_value', claim_value)

        # 쿼리 스트링 제거
        st.query_params.clear()

    # 3. 로그인 상태 여부에 따라 분기
    if st.session_state.get('claim_value') is None:
        # 로그인 정보가 없으면 자동 로그인 시도
        auto_redirect_to_login()
        st.info("로그인 페이지로 이동 중입니다...")
    else:
        # 로그인 완료 화면
        st.success(f"안녕하세요, {st.session_state['claim_value'].get('username')}님!")
        # 여기에 메인 콘텐츠 렌더링

if __name__ == '__main__':
    main()

    # user_id = st.session_state.claim_value['loginid']
       
    try:
        with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
            cursor = conn.cursor()
            qry = f"""
            SELECT *
            FROM v_ipms_ip_info
            WHERE SUB_USER_ID = '{st.session_state['claim_value'].get('loginid')}'
            """    
            cursor.execute(qry)
            user_info = pd.DataFrame(cursor.fetchall(), columns=['ip', 'knox_id', 'user_name', 'dept', 'loc', 'available'])
            cursor.close()
        
        if not user_info.empty and user_info['available'][0] == '승인':
            user_info_cert = 'Y'
        else:
            user_info_cert = 'N'
    except AttributeError:
        pass
    
    
    
    if st.session_state.claim_value != None:
        st.session_state.user = st.session_state.claim_value['loginid']
        if ('Etch기술팀' in st.session_state.claim_value['deptname']) or (user_info_cert == 'Y'):
        # if st.session_state.claim_value['deptname']:

            now_time = datetime.now().replace(second=0, microsecond=0)
            user = st.session_state.user
            history_data = [(now_time, user)]            

           
            with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                cursor = conn.cursor()

                qry = f'''
                    SELECT COUNT(*) FROM user_history
                    WHERE date = %s AND knox_id = %s
                    '''                
                cursor.execute(qry, (now_time, user))
                (count,) = cursor.fetchone()
            
                if count == 0:
                    insert_qry = f''' INSERT INTO user_history VALUES (%s, %s) '''
                    cursor.executemany(insert_qry, history_data)
                    conn.commit()
            
                cursor.close()

    
    # ==========================================================================================================
    ###
    # DB Upload code
    ###
    
            def DBDataLoad(line_id, ver_list, sdwt, desc_list, priority_list, select_sensor):
                try:
                    sql = f"""
                    SELECT DISTINCT ver, recipe_id, update_date, sensor, step, eqp, comment, knox_id
                    FROM pass_history
                    WHERE line_id IN {line_id}
                      AND sdwt = '{sdwt}'
                      AND sensor = '{select_sensor}'
                      AND ver IN {ver_list}
                      AND `desc` IN {desc_list}
                      AND priority IN {priority_list}
                    """.replace(',)',')')
                    with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                        cursor = conn.cursor()
                        cursor.execute(sql)
                        result = pd.DataFrame(cursor.fetchall(), columns=['ver', 'recipe_id', 'update_date', 'sensor', 'step', 'eqp', 'comment', 'knox_id'])
                        result['check'] = True
                        cursor.close()
                    return result
                except Exception as E:
                    print(E)
                    return None
                    
            def DBDataUpLoad(data):
                try:
                    with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                        sql = f"""
                        INSERT INTO `pass_history` 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor = conn.cursor()
                        cursor.executemany(sql, data)
                        conn.commit()
                        cursor.close()
            
                    return False
                except Exception as E:
                    print(E)
                    return True
                
            def DBDataDelete(line_id,sdwt,ver,recipe_id,sensor,step,eqp):
                try:
                    with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                        sql = f"""
                        DELETE 
                        FROM `pass_history`
                        WHERE line_id = '{line_id}'
                          AND sdwt = '{sdwt}'
                          AND ver = '{ver}'
                          AND recipe_id = '{recipe_id}'
                          AND sensor = '{sensor}'
                          AND step = '{step}'
                          AND eqp = '{eqp}'
                        """
                        cursor = conn.cursor()
                        cursor.execute(sql)
                        conn.commit()
                        cursor.close()
                        
                    return False
                except:
                    return True
            
            
            def HitDBDataLoad():
                try:
                    sql = f"""
                    SELECT update_date, line_id, sdwt, file_path
                    FROM hit_history
                    """.replace(',)',')')
                    with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                        cursor = conn.cursor()
                        cursor.execute(sql)
                        result = pd.DataFrame(cursor.fetchall(), columns=['update_date', 'line_id', 'sdwt', 'file_path'])
                        return result
                except Exception as E:
                    print(E)
                    return None
            
            
            def HitDBDataUpLoad(data):
                # print('data: ',data)
                try:
                    with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                        sql = f"""
                        INSERT INTO `hit_history` 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        cursor = conn.cursor()
                        cursor.execute(sql, data)
                        conn.commit()
                        cursor.close()
                        print('업로드완료')
            
                    return False
                except Exception as E:
                    print(E)
                    return True
                    
            
            def HitDBDataDelete(file_path):
                try:
                    with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                        sql = f"""
                        DELETE 
                        FROM `hit_history`
                        WHERE file_path = '{file_path}'
                        """.replace(',)',')')
                        cursor = conn.cursor()
                        cursor.execute(sql)
                        conn.commit()
                        cursor.close()           
                    return False
                except:
                    return True
            
            
            
            def ClickedCategoryUpLoad(history_data):
                # print('data: ',history_data)
                try:
                    with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                        sql = f"""
                        INSERT INTO `clicked_category_history` 
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        cursor = conn.cursor()
                        cursor.execute(sql, history_data)
                        conn.commit()
                        cursor.close()
                        # print('업로드완료')
            
                    return False
                except Exception as E:
                    print(E)
                    return True
            
            
            def TTTM_Load(wono_value):
                sql = f"""
                SELECT DISTINCT wono, llm_summary_body
                FROM llm_ctttm
                WHERE wono = '{wono_value}'
                """.replace(',)',')')
                with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                    cursor = conn.cursor()
                    cursor.execute(sql)
                    result = pd.DataFrame(cursor.fetchall(), columns=['wono', 'llm_summary_body'])
                    cursor.close()
                    return result
            
            
            def format_summary(text):
                # 전처리: 줄바꿈 기준으로 핵심키워드와 요약 추출
                parts = text.strip().split('***')
                keyword_raw = ""
                summary_raw = ""
            
                for part in parts:
                    if "핵심키워드" in part:
                        keyword_raw = part.replace("핵심키워드", "").strip()
                    elif "요약" in part:
                        summary_raw = part.replace("요약", "").strip()
            
                # 출력
                st.write(f"- 핵심키워드 : {keyword_raw}")
                st.write("- 요약내용 :")
            
                # 단어 단위 순차 출력
                output_placeholder = st.empty()
                words = summary_raw.split()
                display_text = ""
            
                for word in words:
                    display_text += word + " "
                    output_placeholder.text(display_text)
                    time.sleep(0.1)
            
            
            
            def toggleChange(_key):
                # print(_key, 'pressed')
                try:
                    if st.session_state.toggle_dict_before[_key]:
                        st.session_state.toggle_dict_before[_key] = False
                    else:
                        st.session_state.toggle_dict_before[_key] = True
                except Exception as E:
                    print(E)
            
            def skipToggleChange(_key):
                # print(_key, 'pressed')
                try:
                    if st.session_state.skip_toggle_dict_before[_key]:
                        st.session_state.skip_toggle_dict_before[_key] = False
                    else:
                        st.session_state.skip_toggle_dict_before[_key] = True
                except Exception as E:
                    print(E)
            
            
            @st.dialog('Skip 사유를 입력하세요')
            def skip(data):
                reason = st.text_input('skip시키는 이유는...')
                if st.button('Skip 등록'):
                    # st.session_state.vote = 'register'
                    if len(data) == 1:
                        data = [item + (reason,) for item in data]
                        DBDataUpLoad(data)
                    else:
                        data = [t + (reason,) for t in data]
                        DBDataUpLoad(data)
                        
                    st.markdown('등록 완료')
                    st.rerun()
            # ==========================================================================================================
            # ======================================================================================================
            
            ##
            # Top of page button
            ##
            
            with stylable_container(
                key="Top",
                css_styles="""
                button{
                    float: right;
                    position: fixed;
                    bottom: 40px;
                    right: 40px;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    font-size: 16px;
                    cursor: pointer;
                    border-radius: 5px;
                    box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.2);
                }
                """
            ):
            
                if st.button("Top"):
                    scroll_to_here(0, key='header')
            
            
            # ======================================================================================================
            
            if 'pre_expander' not in st.session_state:
                st.session_state.pre_expander = True
            
            if 'opened_expander' not in st.session_state:
                st.session_state.opened_expander = None
            
            if 'last_filter' not in st.session_state:
                st.session_state.last_filter = None
            
            if 'all_chart' not in st.session_state:
                st.session_state.all_chart = None
            
            if 'history' not in st.session_state:
                st.session_state.history = None
                
            if 'history_filter' not in st.session_state:
                st.session_state.history_filter = None
                
            if 'select_sensor' not in st.session_state:
                st.session_state.select_sensor = None
                
            if 'change_point' not in st.session_state:
                st.session_state.change_point = None
            
            if 'single_chart' not in st.session_state:
                st.session_state.single_chart = None
            
            if "selected_step_button" not in st.session_state:
                st.session_state.selected_step_button = None
            
            if "selected_ver_button" not in st.session_state:
                st.session_state.selected_ver_button = None
            
            if "output_type" not in st.session_state:
                st.session_state.output_type = None
            
            if 'toggle_dict_all' not in st.session_state:
                st.session_state.toggle_dict_all = None
            
            if 'hit_list' not in st.session_state:
                st.session_state.hit_list = None
            
            if 'hit_del' not in st.session_state:
                st.session_state.hit_del = None
            
            if 'user_uuid' not in st.session_state:
                st.session_state.user_uuid = hashlib.sha256( st.session_state.user.encode() ).hexdigest()
                # st.session_state.user_uuid = str(uuid.uuid4()).replace("-", "")
                st.session_state.hdfs_client = InsecureClient(get_active_namenode(), user='hadoop')
                st.session_state.meta_info = pl.DataFrame()

            if 'min_max_data' not in st.session_state:
                st.session_state.min_max_data = None

            if 'select_min_max_data' not in st.session_state:
                st.session_state.select_min_max_data = None

            if 'hard_spec_search_condition' not in st.session_state:
                st.session_state.hard_spec_search_condition = None
                
            # 251109 추가 ===========
            def commonToggleChange(_key):
                # print(_key, 'pressed')
                try:
                    if st.session_state.common_toggle_dict_before[_key]:
                        st.session_state.common_toggle_dict_before[_key] = False
                    else:
                        st.session_state.common_toggle_dict_before[_key] = True
                except Exception as E:
                    print(E)

            def commonSkipToggleChange(_key):
                # print(_key, 'pressed')
                try:
                    if st.session_state.common_skip_toggle_dict_before[_key]:
                        st.session_state.common_skip_toggle_dict_before[_key] = False
                    else:
                        st.session_state.common_skip_toggle_dict_before[_key] = True
                except Exception as E:
                    print(E)

            if 'common_last_filter' not in st.session_state:
                st.session_state.common_last_filter = None

            if 'common_pre_expander' not in st.session_state:
                st.session_state.common_pre_expander = True

            if 'common_all_chart' not in st.session_state:
                st.session_state.common_all_chart = None

            if 'common_change_point' not in st.session_state:
                st.session_state.common_change_point = None

            if 'common_history' not in st.session_state:
                st.session_state.common_history = None

            if 'common_history_filter' not in st.session_state:
                st.session_state.common_history_filter = None

            if 'common_select_sensor' not in st.session_state:
                st.session_state.common_select_sensor = None

            with open('/appdata/abnormal_trend/pic/common_date.txt', 'r', encoding='utf-8') as file:
                _date_table = [line.strip() for line in file]
                _date_table.sort()
                _latest_date = _date_table[-1]
            common_folder_path = f'/appdata/abnormal_trend/pic/{_latest_date}'
            # =======================
            
            # ======================================================================================================
            folder_path = '/appdata/abnormal_trend/pic/'
            # ======================= 최초 경로 지정 ======================================================================
            
            
            # ======================================================================================================
            ###
            # 최신 날짜 뽑기
            ###
            dates = sorted([i.split('/')[-1] for i in glob.glob('/appdata/abnormal_trend/pic/erd/*')])
            latest_date = dates[-1]
            latest_before_date = dates[-2]
            #with open('/appdata/abnormal_trend/pic/date.txt', 'r', encoding='utf-8') as file:
            #    date_table = [line.strip() for line in file]
            #    date_table.sort()
            #    latest_date = date_table[-1]
            #    latest_before_date = date_table[-2]

            my_variable = f'{folder_path}path/{latest_date}'

            if os.path.isfile(my_variable):
                st.success(f'{latest_date} 기반 데이터 입니다')
                # 알고리즘이 제시간에 정삭 작동 했을때 동작
                new_date_path = f'{folder_path}path/{latest_date}' #수정부분_1222
                stats_path = f'{folder_path}stats/{latest_date}_spider_step_stats_except_v.parquets' #수정부분_1222
            else:
                # 알고리즘이 제시간에 정삭 작동하지 않았을때 직전 데이터 로드
                st.success(f'{latest_before_date} 기반 데이터 입니다')
            
                new_date_path = f'{folder_path}path/{latest_before_date}' #수정부분_1222
                stats_path = f'{folder_path}stats/{latest_before_date}_spider_step_stats_except_v.parquets' #수정부분_1222
            
            
            df_path = pd.read_parquet(new_date_path)          
            
            df_path.loc[df_path['sdwt']=='ER_1213','sdwt'] = 'ER_H1'
       
            
            line_rev = {
                        'Lambda_H1L': 'H1L',
                        'Dreams_H1L': 'H1L',
                        'TERA_H1L': 'H1L',

                        'Lambda_15L': '15L',
                        'Dreams_15L': '15L',
                        'TERA_15L': '15L',

                        'Lambda_16L': '16L',
                        'Dreams_16L': '16L',
                        'TERA_16L': '16L',

                        'Lambda_17L': '17L',
                        'Dreams_17L': '17L',
                        'TERA_17L': '17L',

                        'Lambda_P1D': 'P1D',
                        'Dreams_P1D': 'P1D',
                        'TERA_P1D': 'P1D',

                        'Lambda_P1F': 'P1F',
                        'Dreams_P1F': 'P1F',
                        'TERA_P1F': 'P1F',

                        'Lambda_P23F': 'P23F',
                        'Dreams_P23F': 'P23F',
                        'TERA_P23F': 'P23F',

                        'Lambda_P2D': 'P2D',
                        'Dreams_P2D': 'P2D',
                        'TERA_P2D': 'P2D',

                        'Lambda_P3D': 'P3D',
                        'Dreams_P3D': 'P3D',
                        'TERA_P3D': 'P3D',

                        'Lambda_P3D2': 'P3D2',
                        'Dreams_P3D2': 'P3D2',
                        'TERA_P3D2': 'P3D2',

                        'Lambda_U': 'EndFab',
                        'Dreams_U': 'EndFab',
                        'TERA_U': 'EndFab',
                    }
            
            # 251109 추가 ====
            common_line_rev = {'ER_H1':'12L'}
            # ================
            
            df_path['line_rev'] = df_path['sdwt'].map(line_rev)
    
            df_path.loc[df_path['line_rev'].isnull(),'line_rev'] = '설정 필요'
            
            subset_cols = ['sdwt','desc','ver','recipe_id','date','priority','sensor','eqp','line_rev']
            # 첫 번째 등장 행을 남기고 나머지는 삭제 (keep='first')
            df_path = df_path.drop_duplicates(subset=subset_cols, keep='first').reset_index(drop=True)
            df_path = df_path[~df_path['sensor'].str.startswith('V_MFC')].copy()
        
            cnt_for_ng = pd.crosstab(df_path["sdwt"], df_path["priority"]).reset_index()
            if 'M' not in cnt_for_ng.columns:
                cnt_for_ng['M'] = 0
            try:
                cnt_for_ng['N'] = cnt_for_ng['N'] + cnt_for_ng['X']
            except:
                cnt_for_ng['N'] = cnt_for_ng['N']
            if 'X' in cnt_for_ng.columns:
                cnt_for_ng.drop('X', axis=1, inplace=True)
            
            cols = ['A','B','D','M','N']
            cnt_for_ng["NG"] = cnt_for_ng[cols].sum(axis=1)    
            
            df_stats = pd.read_parquet(stats_path)
            
            # stat_table = df_stats.merge(df_path[['line_id','sdwt','recipe_id','desc']].drop_duplicates(),on=['line_id','recipe_id'],how='left')
            stat_table = df_stats.merge(df_path[['line_rev','sdwt','recipe_id','desc']].drop_duplicates(),on=['recipe_id'],how='left')
            # ======================= 최신업뎃 날짜와 통계값 로드 및 컬럼값 정리================================================
            
            
            
            
            # ======================================================================================================
            stat_table = stat_table.replace(
                {
                    'A' : 'A등급',
                    'B' : 'B등급',
                    'D' : 'D등급',
                    'M' : 'M등급',
                    'N' : 'N등급',
                    'TL' : 'TOTAL'
                }
                )
            # ============================  불러온 Sammury 테이블 컬럼명 변경  ===========================
            
            
            
            
            # ======================================================================================================
            df_result = pd.pivot_table(stat_table[stat_table['priority'] != 'TOTAL'], index=['line_id','sdwt','desc'], columns='priority', values = 'total',aggfunc = 'sum').fillna(0).reset_index()
            df_result = df_result.drop(columns=['X'])
            df_result[df_result.select_dtypes('float').columns] = df_result.select_dtypes('float').astype(int)
            
            df_final = df_result
            df_final.insert(df_final.columns.get_loc('N등급') + 1, 'OK', df_final.loc[:,'A등급':'N등급'].sum(axis=1))
            
            df_final['line_id'] = df_final['sdwt'].replace(line_rev)
            df_final = df_final.drop_duplicates(subset=['line_id', 'sdwt', 'desc']) #새로 추가함
            df_final_sdwt = df_final.groupby(["sdwt"], as_index=False).agg('sum', numeric_only=True)
            df_final_sdwt['line_id'] = df_final_sdwt['sdwt'].replace(line_rev)
            # df_final_sdwt = df_final_sdwt.drop('desc', axis=1) # 251222 주석처리
            df_final_sdwt = df_final_sdwt.sort_values('line_id')
            df_final_sdwt = df_final_sdwt[df_final_sdwt['OK'] != 0] #새로 추가함
            df_final_sdwt = pd.merge(df_final_sdwt,cnt_for_ng[['sdwt','NG']], on=['sdwt'], how='left')
            df_final_sdwt['OK'] = df_final_sdwt['OK'] - df_final_sdwt['NG']
            # df_final_sdwt = df_final_sdwt.drop('line_id', axis=1)
            
            df_final_line = df_final_sdwt.groupby(["line_id"], as_index=False).agg('sum', numeric_only=True) # .drop('sdwt', axis=1) # 251222 주석처리
            
            df_final_sdwt['NG비율'] = (df_final_sdwt['NG'] / (df_final_sdwt['OK'] + df_final_sdwt['NG']) * 100).round(2).astype(str) + '%'
            df_final_sdwt = df_final_sdwt.drop('line_id', axis=1)
            
            df_final_line['NG비율'] = (df_final_line['NG'] / (df_final_line['OK'] + df_final_line['NG']) * 100).round(2).astype(str) + '%'
        
            df_ng_result = pd.pivot_table(stat_table, index=['sdwt','desc','recipe_id'], columns='priority', values = 'ng',aggfunc = 'sum',margins=True).reset_index()
            df_ng_result = df_ng_result.drop(columns=['X'])       
            # ============================  등급별 NG 건수 집계위한 테이블 생성  ==========================
            
            
            
            st.sidebar.page_link("http://etch-spider.net:32603/", label="L0 SPIDER", icon="📈")
            # ======================================================================================================
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.header('')
            with col2:
                st.header('')
            with col3:
                st.html('<a href="http://10.173.129.43:32603/"><img src="https://www.sec.gov/Archives/edgar/data/1041130/000119312518045025/g472619logo_06.jpg"></a>')
            with col4:
                st.header("")
            with col5:
                # st.header("")
                st.markdown(
                """
                <style>
                .top-right {
                    position: absolute;
                    top: 10px;
                    right: 20px;
                    font-size: 20px;
                    color: gray;
                }.small-text {
                    font-size: 15px;
                    font-weight: normal;
                </style>
                <div class="top-right">E기술팀<br>그게 나다</div>
                """,
                unsafe_allow_html=True
            )
            # 초기화면 로고 이미지 표시
            
            
            st.header('FDC 이상 Trend 조회',divider='rainbow')
            
            # ============================  메인페이지 상단 구성  =====================================================
            
            
            
            
            
            # ======================================================================================================
            total = "{:,}".format(int(cnt_for_ng['NG'].sum().sum()))
            ab_grade = "{:,}".format(int(cnt_for_ng["A"].sum()) + int(cnt_for_ng["B"].sum()))
            d_grade = "{:,}".format(int(cnt_for_ng["D"].sum()))
            n_grade = "{:,}".format(int(cnt_for_ng["N"].sum()))
            m_grade = "{:,}".format(int(cnt_for_ng["M"].sum()))
            
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
            col1.metric("모니터링 센서총합", value="{:,}".format(sum(stat_table[stat_table['priority']=='TOTAL']['total'])))
            col2.metric("감지 PPID 갯수", value=df_ng_result.iloc[:-1,2].nunique())
            col3.metric("전체 이상건수", value=total)
            col4.metric("A/B Grade", value=ab_grade)
            col5.metric("D Grade", value=d_grade)
            col6.metric("N Grade", value=n_grade)
            col7.metric("M Grade", value=m_grade)
            # col6.metric("M Grade", value=m_grade, delta = f'{m_grade/total*100:.1f}%', delta_color="off")
            # ============================  상단 종합 건수 표시  =====================================================
            
            
            
            
            # ======================================================================================================
            
            
            tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = \
            st.tabs(["🗃 Summary","📈 자설비 이상감지","📈 동일성 이상감지","📈 공통부 이상감지",
                     "📝 과거 이상감지 이력", "📖사용자 메뉴얼", "📝FDC Hard Limit추천",  "📝수율기반 Hard Limit추천", 
                     "이상감지 수신인 정비"])
            
            
            # ======================================================================================================
            with tab1:

            
                st.header('Summary')
            
            
                def highlight_positive(val):
                    color = 'red' if val > 0 else 'black'  # 0 이상이면 빨간색, 그렇지 않으면 검은색
                    return f'color: {color}'
                # Styler 적용
                df_final = df_final.style.format({'A등급' : '{:,}','B등급' : '{:,}','D등급' : '{:,}','M등급' : '{:,}','N등급' : '{:,}','OK' : '{:,}','ng' : '{:,}' }).applymap(highlight_positive, subset=['ng'])
            
            
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown('라인별 전체 Monitoring 건수')
                    st.dataframe(df_final_line, height=500)
                with col2:
                    st.markdown('SDWT별 전체 Monitoring 건수')
                    st.dataframe(df_final_sdwt, height=1500) #df_ng_result테이블을 Margins를 사용했으므로 All행열을 제외 후 표시
            # ============================  Summart탭에 DataFrame 표시  =====================================================
            
            
            
            # ======================================================================================================
            def single_chart(img_path_result):

                path_str = img_path_result
                dir_part, _, file_name = path_str.rpartition('/')   # dir_part: '/a/b/c', file_name: 'ELOMV2-PM2-dup.png'
                new_file = re.sub(r'-dup(?=\.png$)', '', file_name)
                new_filename = f"{dir_part}/{new_file}" 
                img_path_result = new_filename
                
                parquet_path = img_path_result.replace('.png', '.parquet')
                # 기본값 초기화 (🔥 중요)
                worktype = []
                change_date = []
                
                if os.path.exists(parquet_path):
                    try:
                        change_inform_raw = pd.read_parquet(parquet_path).sort_values('date')
                        worktype = change_inform_raw['work_type'].tolist()
                        change_date = change_inform_raw['date'].tolist()
                    except Exception as e:
                        # 필요 시 로그 출력
                        print(f"parquet read error: {e}")
                else:
                    # 파일 없을 때 (명시적으로 처리)
                    print("parquet file not found")

                start = datetime.now()
                sp = img_path_result.split('/')
                folder_path = '/'+'/'.join(sp[1:-1])
                file_path =  folder_path + '/data.parquet'
                eqp_ch = sp[-1].split('.')[0]
                
                img_data = pd.read_parquet(file_path)
                if 'eqp_cb' in img_data.columns: img_data.drop(columns=['eqp_cb'], inplace=True)
                drawing_df = img_data[(img_data['eqp_id']==eqp_ch.split('-')[0])&(img_data['disp_name']==eqp_ch.split('-')[1])]

                ref_date = latest_date
                drawing_df['act_time'] = pd.to_datetime(drawing_df['act_time'])
                ref_date = pd.to_datetime(ref_date)
                
                # 기준 시간 계산
                start_time = ref_date - timedelta(hours=26)
                
                # 색상 조건 컬럼 생성
                drawing_df['구분'] = drawing_df['act_time'].apply(
                    lambda x: '이상구간' if start_time <= x <= ref_date else 'Ref'
                )
                
                # Plotly
                fig = px.scatter(
                    drawing_df,
                    x="act_time",
                    y=img_data.columns[-1],
                    color='구분',
                    color_discrete_map={
                        '이상구간': 'red',
                        'Ref': 'gray'
                    },
                    hover_data=[img_data.columns[-1], 'root_lot_id', 'wafer_id']
                )
                
                fig.update_layout(
                    title=img_data.columns[-1],
                    title_x=0.5,
                    title_xanchor='center'
                )

                for i, (wt, dt) in enumerate(zip(worktype, change_date)):
                    dt = pd.to_datetime(dt)
                
                    # 👉 세로선
                    fig.add_shape(
                        type="line",
                        x0=dt, x1=dt,
                        y0=0, y1=1,
                        xref='x',
                        yref='paper',
                        line=dict(color="green", dash="dash")
                    )
                
                    # 👉 텍스트
                    fig.add_annotation(
                        x=dt,
                        y=1,
                        xref='x',
                        yref='paper',
                        text=wt,
                        showarrow=False,
                        font=dict(color="green", size=11),
                        yanchor="bottom"
                    )
                
                fig.update_yaxes(title=None)
                
                fig.update_layout(width=400, height=300)

                
                st.plotly_chart(fig, use_container_width=True)
            
            
            
            def all_chart(file_info,
                    eqp_col="eqp",
                    lot_col='lot_wf',
                    time_col="act_time",
                    value_col="value",
                    time_format="%Y-%m-%d",           # "2025-05-17 13:23:44"
                    gap_ratio=0.05,                   # 구간 사이 간격 (전역 span 대비). 0이면 딱 붙음
                    marker_size=5,
                    tick_fracs=(0.5, 1), # (0.2, 0.5, 0.8),       # ✅ 구간별 20/50/80% 지점 3개만
                    hide_xticks_until_zoom=False,
                    mode=0,
                    data=None,
                    min_max_data=(),
                 ):# ✅ (3) 기본 뷰에서는 x축 레이블 숨김):
        
                    
                    path_str = file_info
                    dir_part, _, file_name = path_str.rpartition('/')   # dir_part: '/a/b/c', file_name: 'ELOMV2-PM2-dup.png'
                    new_file = re.sub(r'-dup(?=\.png$)', '', file_name)
                    new_filename = f"{dir_part}/{new_file}" 
                    file_info = new_filename
                
                #  --- 필요 컬럼 생성 ---
                    if not mode:
                        file_info_split = file_info.split('/')
                        file_info_split_change = file_info_split.copy()
                        file_info_split_change[-1] = 'data.parquet'
                        file_info_final = "/".join(file_info_split_change)
                        eqp_id = file_info_split[-1].split('.')[0]
                        sensor = file_info_split[-3] + '_' + file_info_split[-2]
                       
                        data = pd.read_parquet(file_info_final)
                    
                    #try:
                    #    if not mode:
                    #        # 동일성 그래프 그리는 코드 변경 후 데이터가 많으면 너무 느려져서, 동일성 그릴 때는 30일치만 그려지게 수정
                    #        from_time = datetime.now() - timedelta(days=30)
                    #        from_time = from_time.strftime("%Y-%m-%d %H:%M:%S")
                    #        data = data[data['act_time'] >= from_time]
                    #except:
                    #    print('err')
                    
                    if not mode:
                        df = data.copy()
                        df = df.rename(columns={sensor:'value'})
                        if eqp_col not in df.columns: df[eqp_col] = df['eqp_id']+'-'+df['disp_name']
                        if 'root_lot_id' in df.columns:
                            if 'lot_wf' not in df.columns: df['lot_wf'] = df['root_lot_id']+'-'+df['wafer_id']
                        elif 'lotid' in df.columns:
                            if 'lot_wf' not in df.columns: df['lot_wf'] = df['lotid']+'-'+df['wafer_id']
                        # --- 결측 정리(필요시) ---
                        df = df.dropna(subset=[eqp_col, time_col, value_col])
                        df.sort_values(eqp_col,inplace=True)
                        df.reset_index(drop=True,inplace=True)
                    else:
                        df = data
                        df = \
                        df.rename(
                            {'param_value':'value'}
                        ).with_columns(
                            pl.col('act_time').str.strptime(pl.Datetime, "%Y-%m-%d %H:%M:%S%.f").dt.truncate("1s"),
                            (pl.col('eqp_id')+'-'+pl.col('disp_name')).alias(eqp_col)
                        ).sort([eqp_col,'act_time']).collect().to_pandas()
                    
                    
                    # --- act_time 파싱: 이미 datetime이면 유지, 아니면 지정 포맷으로 파싱 ---
                    if not pd.api.types.is_datetime64_any_dtype(df[time_col]):
                        df[time_col] = pd.to_datetime(df[time_col], format=time_format, errors="coerce")
                    else:
                        df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
                    bad = df[time_col].isna().sum()
                    if bad > 0:
                        raise ValueError(
                            f"[{time_col}] 파싱 실패(NaT) {bad}개가 있어요. "
                            f"time_format='{time_format}' 또는 원본 값을 확인해주세요."
                        )
                
                    # --- eqp 순서: 각 eqp의 첫 act_time 기준 정렬(보기 자연스러움) ---
                    eqps = df.drop_duplicates(eqp_col)[eqp_col].to_list()
                    eqp_to_i = {e: i for i, e in enumerate(eqps)}
                
                    # --- 전역 act_time span(모든 eqp 구간 폭 동일하게) ---
                    tmin = df[time_col].min()
                    tmax = df[time_col].max()
                    duration = (tmax - tmin)
                    span = duration.total_seconds()


# ===== END: app_first_part.py =====


# ===== START: plotly_to_hard_spec_section.py =====

            with tab2:
                st.subheader('조회조건 설정')
                st.write('(감지되지 않는 트렌드 제보해주시면 업데이트하겠습니다.)')
                # =========================================================================================================
                with st.container(border=True):
            
                    try:
                        # sorted(df_path['line_rev'].unique()) # ← 나중에 라인 추가되면 매핑 하는 거 필요. 
                        # st.markdown('P23F, P3D 서버 과부하로 인한 데이터 오류로 공사중입니다 (~5/15까지) 죄송합니다.')
                        select_line = st.segmented_control(
                        "라인 선택",
                        ['H1L','15L','16L','17L','P1F','P1D','P23F','P2D','P3D','P3D2'], key='line'
                        )
                        select_line_upload = select_line #클릭이력 저장용 변수
                   
                        selected_keys = [key for key, value in line_rev.items() if value == select_line] #선택한 라인 내 sdwt 리스트
                        select_sdwt = st.segmented_control("분임조 선택", selected_keys, key='sdwt')
                        
                        if select_sdwt: 
                            _p = f'{folder_path}path/{select_line}/{select_sdwt}/df_path.parquet'
                            if not os.path.exists(_p): 
                                df_path = pd.DataFrame()
                            else:
                                df_path = pd.read_parquet(_p)
                        
            
                        if select_line and select_sdwt:
                            if 'P4' in select_line:
                                df_path.loc[df_path['priority']=='X','priority'] = 'N'
                            if (len(df_path) == 0) or (set(df_path['priority'].unique()) == {'X'} and 'P4' not in select_line):
                                st.markdown('이상감지 건수가 없습니다')
            
                            else:         
                                
                                select_line = df_path['line_rev'].unique()
                
                                data_table = df_path[~df_path['sensor'].str.startswith('V_MFC')].copy()        
                                data_table = pl.from_pandas(data_table)
                                data_table = data_table.rename({'priority': 'grade'})
                
                
                                grade_data = sorted(list(data_table['grade'].unique()))
                                if 'X' in grade_data: grade_data.remove('X')

                                select_grade = grade_data               
                
                
                                filtered_grade_table =  data_table.filter(pl.col('grade').is_in(select_grade))
                                
                                select_list_step = sorted(filtered_grade_table['desc'].unique())
                                if select_grade:
                                    select_list_step.insert(0,'ALL')

                                select_step = sorted(filtered_grade_table['desc'].unique())               
                
                                # ver_path = step_path + '/' + select_step
                                filtered_step_table = filtered_grade_table.filter(pl.col('desc').is_in(select_step))
                                select_list_vr = sorted(filtered_step_table['ver'].unique())
                                if select_step:
                                    select_list_vr.insert(0,'ALL')
                                if select_list_vr == []:
                                    st.session_state.selected_ver_button = []                    
                                select_vr = st.segmented_control(
                                                                "버전 선택 (복수선택 가능, ALL 조회 시 속도가 많이 느려집니다)",
                                                                select_list_vr, 
                                                                key='selected_ver_button', 
                                                                selection_mode="multi",
                                                                on_change=updateVerSelect
                                                                )
                                if select_vr == 'ALL': 
                                    select_vr = sorted(filtered_step_table['ver'].unique())           
                
                                #=======================================================================================
                                if select_vr:
                                    for_grade = select_grade
                                #====조회용 for문의 grade분류위한 함수, grade가 최종선택되야 Selectbox가 container별로 들어감=============
                
                
                                 #====기존코드 0504=============
                                # total_table = filtered_step_table.filter(pl.col('ver').is_in(select_vr))
                                # for_download = data_table.drop("file_path")
                                #====기존코드 0504=============

                                total_table = filtered_step_table.filter(pl.col('ver').is_in(select_vr)).sort('recipe_id')
                                total_table_for_skip = total_table.to_pandas()
                                total_table_for_skip['eqp'] = total_table_for_skip['eqp'].str.replace(r'\.png$', '', regex=True)
                                total_table = total_table.unique(subset=['sdwt','desc','ver','recipe_id','date','grade','sensor','eqp','line_rev'],keep='first').sort('sdwt', descending=True)
                                
                                for_download = data_table.drop("file_path")

                                
                                csv = for_download.write_csv().encode("utf-8")
                                
                                if st.session_state.last_filter != f'{select_line}/{select_sdwt}/{select_step}/{select_vr}/{select_grade}':
                                    st.session_state.pre_expander = None
                                    st.session_state.all_chart = None
                                    st.session_state.change_point = None
                                    st.session_state.toggle_dict_before = {}
                                    st.session_state.toggle_dict = {}
                                    
                                    st.session_state.history = {}
                                    
                                    st.session_state.skip_toggle_dict_before = {}
                                    st.session_state.skip_toggle_dict = {}
                                    
                                    st.session_state.select_sensor = {}
                                    
                                st.session_state.last_filter = f'{select_line}/{select_sdwt}/{select_step}/{select_vr}/{select_grade}'
            
            
                    except TypeError:
                        pass
            
            
            
                #print('session',st.session_state)
            
                #if st.session_state.open_container:
                try:
                    # =========================================================================================================
                    st.subheader("")
                    st.subheader(f'조회결과 (총{len(total_table)}건)', divider=True)
                    # # ==================================필터조건 모두 선택 후의 파일경로 구성============================================
                    grade = st.radio('센서 등급', for_grade, horizontal = True)
                    # select_eqp_sensor = st.radio('조회조건', ['스탭별 조회','센서별 조회','설비별 조회'], horizontal = True)
                    select_eqp_sensor = st.radio('조회조건', ['스탭별 조회'], horizontal = True)
                    
                    if grade:
                        st.download_button(label="전체이상감지List Download", data=csv, file_name="abnormal_list.csv", type="primary", icon=":material/download:")
                        col1, col2 = st.columns([1.5, 2])
                        with col1:
                            with st.container(border=True):
                        # =========================================================================================================
                                filtered_grade_table = total_table.filter(pl.col('grade').is_in([grade])).sort('sensor') #Grade별 Dwawing위한 for문에서 grade별 이상감지 전체 테이블
                                filtered_result_list = filtered_grade_table.to_numpy().tolist() #각 row 단위 리스트화
                                filtered_grade_table_pandas = filtered_grade_table.to_pandas() # 판다스로 데이터프레임으로 전환 (센서 선택 시 폴라스 데이터 프레임으로 하면 꼬임)
            
            
                                filtered_grade_table_count = filtered_grade_table_pandas['sensor'].value_counts().reset_index() #센서별 전체 건수 (센서 선택 시 표현위해)
                                filtered_grade_table_count.columns = ['sensor', 'count']
                                filtered_grade_table_count.rename(columns={"count": "이상 건수"}, inplace=True)
            
                                filtered_eqp_table_count = filtered_grade_table_pandas['eqp'].value_counts().reset_index()
                                filtered_eqp_table_count.columns = ['eqp', 'count'] 
                                filtered_eqp_table_count.rename(columns={"count": "이상 건수"}, inplace=True)

                                filtered_step_table_count = filtered_grade_table_pandas['desc'].value_counts().reset_index().sort_values(by='desc', ascending=False)
                                filtered_step_table_count.columns = ['desc', 'count'] 
                                filtered_step_table_count.rename(columns={"count": "이상 건수"}, inplace=True)
                    
                                filtered_eqp_table_count['eqp'] = filtered_eqp_table_count['eqp'].str.replace('.png','',regex=False) 
                        # ====================================== selectbox에 넣기위한 리스트 생성 (건수 표기위해 별도 가공) =======================================
            
            
                                st.markdown(f'{grade}등급 (총{len(filtered_result_list)}건)')

                                if select_eqp_sensor == '센서별 조회':
            
                                    # select_sensor = st.selectbox('', radio_count_list,  placeholder='조회 센서를 선택하세요', key=f'sel_{idx}',index=None)
                                    gb = GridOptionsBuilder.from_dataframe(filtered_grade_table_count)
                                    gb.configure_default_column(autoWidth=True)
                                    gb.configure_column("이상 건수", width=80)
                                    gb.configure_column("sensor", filter=True)
                                    gb.configure_side_bar()
                                    gb.configure_pagination(enabled=True)
                                    gb.configure_selection('single')  # 단일 행 선택
                                    grid_options = gb.build()
                                    
                                    # AgGrid 렌더링
                                    grid_response = AgGrid(
                                        filtered_grade_table_count,
                                        gridOptions=grid_options,
                                        update_mode=GridUpdateMode.SELECTION_CHANGED,
                                        height=400,
                                        fit_columns_on_grid_load=True,
                                        use_container_width=False,
                                        # width=500,
                                        key=f'sel_{grade}'
                                    )
                
                                    
                                    result = grid_response['selected_rows']
                                    select_sensor = result['sensor'][0]


                                elif select_eqp_sensor == '설비별 조회':

                                    gb = GridOptionsBuilder.from_dataframe(filtered_eqp_table_count)
                                    gb.configure_default_column(autoWidth=True)
                                    gb.configure_column("이상 건수", width=80)
                                    gb.configure_column("eqp", filter=True)
                                    gb.configure_side_bar()
                                    gb.configure_pagination(enabled=True)
                                    gb.configure_selection('single')  # 단일 행 선택
                                    grid_options = gb.build()
                                    
                                    # AgGrid 렌더링
                                    grid_response = AgGrid(
                                        filtered_eqp_table_count,
                                        gridOptions=grid_options,
                                        update_mode=GridUpdateMode.SELECTION_CHANGED,
                                        height=400,
                                        fit_columns_on_grid_load=True,
                                        use_container_width=False,
                                        # width=500,
                                        key=f'sel_{select_eqp_sensor}_1'
                                    )                
                                    
                                    result = grid_response['selected_rows']
                                    select_eqp = result['eqp'][0]

                                    if select_eqp:
                                        filtered_grade_eqp_table = total_table.filter(pl.col('grade').str.contains(grade) & pl.col('eqp').str.contains(select_eqp)).sort('eqp') #Grade별 Dwawing위한 for문에서 grade별 이상감지 전체 테이블
                                        filtered_result_list = filtered_grade_eqp_table.to_numpy().tolist() #각 row 단위 리스트화
                                        filtered_grade_eqp_table_pandas = filtered_grade_eqp_table.to_pandas() # 판다스로 데이터프레임으로 전환 (센서 선택 시 폴라스 데이터 프레임으로 하면 꼬임)
                    
                                        filtered_grade_eqp_table_count = filtered_grade_eqp_table_pandas['sensor'].value_counts().reset_index() #센서별 전체 건수 (센서 선택 시 표현위해)
                                        filtered_grade_eqp_table_count.columns = ['sensor', 'count']  
                                        filtered_grade_eqp_table_count.rename(columns={"count": "이상건수"}, inplace=True)
            
                                        with col2:
                                            with st.container(border=True):
                                                st.markdown(' ')
                                                st.markdown(' ')
                                                st.markdown(' ')
                                                gb = GridOptionsBuilder.from_dataframe(filtered_grade_eqp_table_count)
                                                gb.configure_default_column(autoWidth=True)
                                                gb.configure_column("이상건수", width=80)
                                                gb.configure_column("sensor", filter=True)
                                                gb.configure_side_bar()
                                                gb.configure_pagination(enabled=True)
                                                gb.configure_selection('single')  # 단일 행 선택
                                                grid_options = gb.build()
                                                
                                                # AgGrid 렌더링
                                                grid_response = AgGrid(
                                                    filtered_grade_eqp_table_count,
                                                    gridOptions=grid_options,
                                                    update_mode=GridUpdateMode.SELECTION_CHANGED,
                                                    height=400,
                                                    fit_columns_on_grid_load=False,
                                                    use_container_width=False,
                                                    # width=500,
                                                    key=f'sel_{select_eqp}_2'
                                                )
                
                                                result = grid_response['selected_rows']
                                                select_sensor = result['sensor'][0]
                                                select_eqp_final = f'{select_eqp}.png'

                                elif select_eqp_sensor == '스탭별 조회':

                                    gb = GridOptionsBuilder.from_dataframe(filtered_step_table_count)
                                    gb.configure_default_column(autoWidth=True)


# ===== END: third_question_section.py =====


# ===== START: fourth_question_section.py =====

                                    gb.configure_column("이상 건수", width=80)
                                    gb.configure_column("desc", filter=True)
                                    gb.configure_side_bar()
                                    gb.configure_pagination(enabled=True)
                                    gb.configure_selection('single')  # 단일 행 선택
                                    grid_options = gb.build()
                                    
                                    # AgGrid 렌더링
                                    grid_response = AgGrid(
                                        filtered_step_table_count,
                                        gridOptions=grid_options,
                                        update_mode=GridUpdateMode.SELECTION_CHANGED,
                                        height=400,
                                        fit_columns_on_grid_load=True,
                                        use_container_width=False,
                                        # width=500,
                                        key=f'sel_{select_eqp_sensor}_2'
                                    )                
                                    
                                    result = grid_response['selected_rows']
                                    select_step_for_image = re.sub(r"\s*\[.*?\]", "", result['desc'][0]).strip()

                                    if select_step_for_image:
                                        # 1️⃣ Polars → Pandas 변환
                                        total_table_pd = total_table.to_pandas()
                                        
                                        # 2️⃣ 필터 + 정렬
                                        filtered_grade_step_table_pandas = (
                                            total_table_pd[
                                                total_table_pd['grade'].str.contains(grade, na=False) &
                                                total_table_pd['desc'].str.contains(select_step_for_image, na=False)
                                            ]
                                            .sort_values(by='desc')
                                            .reset_index(drop=True)
                                        )
                    
                                        filtered_grade_step_table_count = filtered_grade_step_table_pandas['sensor'].value_counts().reset_index() #센서별 전체 건수 (센서 선택 시 표현위해)
                                        filtered_grade_step_table_count.columns = ['sensor', 'count']
                                        filtered_grade_step_table_count = filtered_grade_step_table_count.sort_values(by='sensor', ascending=False)
                                        filtered_grade_step_table_count.rename(columns={"count": "이상건수"}, inplace=True)
            
                                        with col2:
                                            with st.container(border=True):
                                                st.markdown(' ')
                                                st.markdown(' ')
                                                st.markdown(' ')
                                                gb = GridOptionsBuilder.from_dataframe(filtered_grade_step_table_count)
                                                gb.configure_default_column(autoWidth=True)
                                                gb.configure_column("이상건수", width=80)
                                                gb.configure_column("sensor", filter=True)
                                                gb.configure_side_bar()
                                                gb.configure_pagination(enabled=True)
                                                gb.configure_selection('single')  # 단일 행 선택
                                                grid_options = gb.build()
                                                
                                                # AgGrid 렌더링
                                                grid_response = AgGrid(
                                                    filtered_grade_step_table_count,
                                                    gridOptions=grid_options,
                                                    update_mode=GridUpdateMode.SELECTION_CHANGED,
                                                    height=400,
                                                    fit_columns_on_grid_load=False,
                                                    use_container_width=False,
                                                    # width=500,
                                                    key=f'sel_{select_step_for_image}_2'
                                                )
                
                                                result = grid_response['selected_rows']
                                                select_sensor = result['sensor'][0]
                                                select_step_final = select_step_for_image

                            
                        with st.container(border=True):
                            if select_sensor:
                                filtered_final_image_list = [item for item in filtered_result_list if select_sensor == item[6]] #grade별 필터한 이상감지 리스트를 각 컬럼별 리스트화
                                # if select_eqp_final:
                                #     filtered_final_image_list = [item for item in filtered_result_list if select_sensor == item[6] and select_eqp_final == item[8]]
                                if select_step_final:
                                    filtered_final_image_list = [item for item in filtered_final_image_list if select_step_final in item[1]]

                                ######################클릭이력
                                history_data = (select_line_upload, select_sdwt, json.dumps(select_grade), select_sensor, datetime.now(), st.session_state.user)
                                ClickedCategoryUpLoad(history_data)
                                #####################
            
                                
                                
                                #####################
                                # History data load #
                                #####################
                                filter_sp = st.session_state.last_filter.split('/')
                                line_id = tuple(eval(filter_sp[0]))
                                converted_line_id = tuple(line_id[0][i:i+4] for i in range(0, len(line_id[0]), 4))
                                sdwt = filter_sp[1]
                                ver_list = tuple(eval(filter_sp[3]))
                                priority_list = tuple(eval(filter_sp[4]))
                                _filter = [line_id, ver_list, sdwt, select_step, priority_list]
                                if st.session_state.history_filter != _filter:
                                    st.session_state.history_filter = _filter
            
                                    
                                # print('세션 스테이트 센서', st.session_state.select_sensor)
                                # print('sensor 선택', select_sensor)   
                                # 선택된 센서를 기준으로, 이전 센서와 다른 센서 선택 시 toggle dict reset
                                
                                try:
                                    if grade not in st.session_state.select_sensor:
                                        st.session_state.select_sensor[grade] = ''
                                    
                                    if st.session_state.select_sensor[grade] != select_sensor:
                                        st.session_state.select_sensor[grade] = select_sensor
                                        
                                        try:
                                            st.session_state.toggle_dict = {k: v for k, v in st.session_state.toggle_dict.items() if k.split('_')[1] != grade}
                                            st.session_state.toggle_dict_before = {k: v for k, v in st.session_state.toggle_dict_before.items() if k.split('_')[1] != grade}
                                            
                                            st.session_state.skip_toggle_dict = {k: v for k, v in st.session_state.skip_toggle_dict.items() if k.split('_')[2] != grade}
                                            st.session_state.skip_toggle_dict_before = {k: v for k, v in st.session_state.skip_toggle_dict_before.items() if k.split('_')[2] != grade}
                                            
                                        except Exception as E:
                                            print('='*20)
                                            print('2 err')
                                            print(E)
                                            print('='*20)
                                        
                                        try:
                                            print('dbTable확인용 :',line_id, ver_list, sdwt, tuple(select_step), priority_list, select_sensor)
                                            dbTable = DBDataLoad(line_id, ver_list, sdwt, tuple(select_step), priority_list, select_sensor)
                                            print('pass확인용 :',dbTable)
                                            st.session_state.history[grade] = DBDataLoad(line_id, ver_list, sdwt, tuple(select_step), priority_list, select_sensor)
                                            # print(converted_line_id, ver_list, sdwt, tuple(select_step), priority_list, select_sensor)
                                            file_path_info = pd.DataFrame([(i[9],i[2],i[3],i[6],i[7],i[8].split('.')[0], False) for i in filtered_final_image_list], columns=['file_path','ver','recipe_id','sensor','step','eqp','check'])
                                            #print('file_path_info')
                                            #print('*'*10)
                                            keys = ['ver', 'recipe_id','sensor','step','eqp']
                                            
                                            file_path_df = (
                                                pd.concat(
                                                    [
                                                        file_path_info.drop(columns=['file_path']),
                                                        st.session_state.history[grade][
                                                            st.session_state.history[grade]['update_date'] > datetime.now() - timedelta(days=3)
                                                        ].drop(columns='update_date')
                                                    ],
                                                    axis=0
                                                )
                                                .groupby(keys, as_index=False)
                                                .agg(check=('check', 'max'))
                                                .merge(
                                                    file_path_info.drop(columns=['check']),
                                                    on=keys,
                                                    how='left'
                                                )
                                            )
       
                                            st.session_state.history[grade] = file_path_df[~file_path_df['file_path'].isnull()]

                                        except Exception as E:
                                            print('='*10)
                                            print('1 err')
                                            print(E)
                                            print('='*10)
                                except Exception as E:
                                    print(E)                        
                                # # # # # # # # # # # 
            
            
            
                                
                            # ===========================================================================================================================
                                for eqp_list in sorted(st.session_state.history[grade][st.session_state.history[grade]['check'] == False]['eqp'].unique()):
                                    for_enu = st.session_state.history[grade][(st.session_state.history[grade]['check'] == False) & (st.session_state.history[grade]['eqp'] == eqp_list.split('.')[0])]
                                    #skip체크없는 최종 이상감지 리스트(file_path_df)에 선택한 센서, skip유무, eqp까지 필터 후 변수에 저장 (for문에 직접 넣으려니 너무 길어서....)
                                    with st.expander(f'{eqp_list.split(".")[0]} ({len(for_enu)}건)', expanded=False):
                                    
                                        
                                        _key_all=f'toggle_{str(grade)}_{eqp_list}_{st.session_state.last_filter}' # key값을 변수에 저장 (여러곳에 사용)                                       
                                        on = st.toggle('EQP All Skip (Skip 리스트로 이동하여 3일간 동일 이상건 제외)', key=_key_all)
                                        if on:
                                            if st.session_state.toggle_dict_all != _key_all:
                                                st.session_state.toggle_dict_all = _key_all
                                                   
                                                upload_data_list = []
                                                for path_values in (for_enu['file_path'].values):
                                                    img_path = path_values
                                                    img_path_sp = img_path.split('/') #차트에 각종 정보 표현위해 '/'구분자로 쪼개어 경로정보 list에 저장
                                                    data = (line_rev[img_path_sp[6]],img_path_sp[8],img_path_sp[6],img_path_sp[7],
                                                                        img_path_sp[9],img_path_sp[5],img_path_sp[10],img_path_sp[11],
                                                                        img_path_sp[12],img_path_sp[13].split('.')[0],st.session_state.user,datetime.now())
                                                    upload_data_list.append(data)
                                                skip(upload_data_list)
            
                                            else: st.session_state.toggle_dict_all == None
                                                
            
                                        with st.container(border=True):   
                                            cols = st.columns(2)
                                            for i, path_values in enumerate(for_enu[['file_path','check']].values):
                                                img_path = path_values[0] #차트 drwing위한 이미지 경로 변수 저장
                                                img_path_sp = img_path.split('/') #차트에 각종 정보 표현위해 '/'구분자로 쪼개어 경로정보 list에 저장
                                                
                                                with cols[i % 2]:
                                                    with st.container(border=True):
                                                        img_path_result = img_path.replace('pic_server2', 'pic') #이미지 경로(img_path) 내 일부 문구 변경
                                                        # print('img_path_sp', img_path_sp)
                                                        st.markdown(img_path_sp[6] + ' / ' + img_path_sp[7] + ' / ' + img_path_sp[8] + ' / ' + img_path_sp[9] + ' / ' + img_path_sp[-1].split('.')[0])
                                              
                                                        ###########################
                                                        # toggle dict 데이터 확인 #
                                                        ###########################
                                                        
                                                        _key=f'toggle_{str(grade)}_{path_values}_{str(i)}_{st.session_state.last_filter}' # key값을 변수에 저장 (여러곳에 사용)
                                                        
                                                        if _key not in st.session_state.toggle_dict:
                                                            check_value = path_values[1]
                                                            st.session_state.toggle_dict_before[_key] = check_value
                                                            on = st.toggle('Skip (Skip 리스트로 이동하여 3일간 동일 이상건 제외)', key=_key, value=check_value, on_change=toggleChange, args=(_key,))
                                                            
                                                            st.session_state.toggle_dict[_key] = check_value
                                                            # print('on :',on)
                                                            # print('check :', check_value)
                                                            # print('dict :',st.session_state.toggle_dict[_key])
                                                        else:
                                                            check_value = st.session_state.toggle_dict_before[_key]
                                                            on = st.toggle('Skip (Skip 리스트로 이동하여 3일간 동일 이상건 제외)', key=_key, value=check_value, on_change=toggleChange, args=(_key,))
                                                            
                                                            # print('on :',on)
                                                            # print('check :', check_value)
                                                            # print('dict :',_key)
                                                            
                                                            if st.session_state.toggle_dict[_key] != on:
                                                                data = [(line_rev[img_path_sp[6]],img_path_sp[8],img_path_sp[6],img_path_sp[7],
                                                                        img_path_sp[9],img_path_sp[5],img_path_sp[10],img_path_sp[11],
                                                                        img_path_sp[12],img_path_sp[13].split('.')[0],st.session_state.user,datetime.now())]
                                                                # print(data)
                                                                if  on == False:
                                                                    # print('on → off')
                                                                    data = data[0]
                                                                    if DBDataDelete(data[0],data[1],data[2],data[4],data[7],data[8],data[9]):
                                                                        st.write('관리자 문의 필요')
                
                                                                elif on == True:
                                                                    skip(data)
                                                                                
                                                                        
                                                            st.session_state.toggle_dict[_key] = on
                                                            st.session_state.toggle_dict_before[_key] = on
                                                        # # # # # # # # # # # # # #                                              
                                                        
                                                        # if on:
                                                            # st.write(img_path)
                                                            # print(img_path[0])
                
                                                        # st.image(img_path_result)
                                                        single_chart(img_path_result)
                                                                      
                
                                                        bt_key = key=f'butt_{grade}_{path_values}_{str(i)}_{st.session_state.last_filter}'
                                                        
                                                        
                                                        col1, col2, col3, col4 = st.columns(4)
                                                        
            
                                                        with col1:
                                                            if st.button('동일성차트', bt_key):
                                                                if st.session_state.all_chart != bt_key:
                                                                    st.session_state.all_chart = bt_key
                                                                else:
                                                                    st.session_state.all_chart = None
            
                                                                if st.session_state.output_type != bt_key+"matplotlib":
                                                                    st.session_state.output_type = bt_key+"matplotlib"
                                                                else:
                                                                    st.session_state.output_type = None                                                
            
                                                                   
            
            
                                                        with col2:                                       
                                                            if st.button('변경점 리스트', bt_key+'_changepoint'):
                                                                if st.session_state.change_point != bt_key+'_changepoint':
                                                                    st.session_state.change_point = bt_key+'_changepoint'
                                                                else:
                                                                    st.session_state.change_point = None
            
                                                                if st.session_state.output_type != bt_key+"markdown":
                                                                    st.session_state.output_type = bt_key+"markdown"
                                                                else:
                                                                    st.session_state.output_type = None
                                                
            
            
                                                        with col3:
                                                            eqpid_for_timeline = img_path_sp[-1].split('.')[0].replace('PM', '')
                                                            st.link_button('타임라인', f'https://etchdx.net:8004/timeline/{eqpid_for_timeline}')
                                                        
                                                        with col4:
                                                            if st.button('이력저장', bt_key+'_hitlist'):
                                                                if st.session_state.hit_list != bt_key+'_hitlist':
                                                                    st.session_state.hit_list = bt_key+'_hitlist'
                                                                else:
                                                                    st.session_state.change_point = None
            
                                                                if st.session_state.output_type != bt_key+"markdown_hit":
                                                                    st.session_state.output_type = bt_key+"markdown_hit"
                                                                    for_bu_file = img_path_result.replace('/','#')
                                                                    save_root = "/appdata/abnormal_trend/pic/backup/"
                                                                    save_path = os.path.join(save_root, for_bu_file)
                                                                    shutil.copy2(img_path_result, save_path)
                                                                    
                                                                    data = (img_path_result.split('/')[5], select_line[0] if isinstance(select_line, np.ndarray) else select_line,
                                                                            img_path_result.split('/')[6],img_path_result,st.session_state.user,datetime.now())
                                                                    HitDBDataUpLoad(data)
                                                                    st.markdown('저장 완료')
                                                                else:
                                                                    st.session_state.output_type = None
            
                                                        
            
            
                                                        if st.session_state.output_type == bt_key+"matplotlib":
                                                            all_chart(img_path_result)                                                             
                                                        
                                                    
                                                        elif st.session_state.output_type == bt_key+"markdown":
                                                            try:
                                                                change_inform_raw = pd.read_parquet(img_path_result.replace('.png','.parquet')).sort_values('date')

                                                                for index, row in change_inform_raw.iterrows():                                                              
                                                                    st.markdown(f"[📘 {row['date']}  [{row['work_type']}] : {row['desc']}]({row['ctttm_url']})", unsafe_allow_html=True)
            
            
                                                            except:
                                                                st.markdown('😔 변경점 없음')
            
            
                                
            
                                # ============================    Skip버튼 미설정 Drwing      =============================================
            
            
            
            
            
            
                                # ===========================================================================================================================
            
                                for_enu_true = st.session_state.history[grade][st.session_state.history[grade]['check'] == True]
                                with st.expander(f'Skip 리스트 ({len(for_enu_true)} 건)', expanded=False):
                                
                                    with st.container(border=True):
                                        cols = st.columns(2)
                                        for i, path_values in enumerate(for_enu_true[['file_path','eqp','recipe_id','check']].values):
                                            img_path = path_values[0]
                                            img_path_sp = img_path.split('/')
                                            img_path_comment = path_values[1]
                                            img_path_knoxid = path_values[2]
                                            
                                            with cols[i % 2]:
                                                with st.container(border=True):
                                                    img_path_result = img_path.replace('pic_server2', 'pic')
                                                    st.markdown(img_path_sp[6] + ' / ' + img_path_sp[7] + ' / ' + img_path_sp[8] + ' / ' + img_path_sp[-1].split('.')[0])
                                                    # st.markdown(f'skip사유 (등록자) : {img_path_comment} / {img_path_knoxid}')
                                                   
                                                    
                                                      
                                                    ###########################
                                                    # toggle dict 데이터 확인 #
                                                    ###########################
                                                    
                                                    _key=f'skip_toggle_{str(grade)}_{str(i)}_{path_values}_{st.session_state.last_filter}'
                                                    
                                                    if _key not in st.session_state.skip_toggle_dict:
                                                        check_value = path_values[3]
                                                        st.session_state.skip_toggle_dict_before[_key] = check_value
                                                        on = st.toggle('Skip (Skip 리스트로 이동하여 3일간 동일 이상건 제외)', key=_key, value=check_value, on_change=skipToggleChange, args=(_key,))
                                                        st.session_state.skip_toggle_dict[_key] = check_value
                                                    else:
                                                        check_value = st.session_state.skip_toggle_dict_before[_key]
                                                        on = st.toggle('Skip (Skip 리스트로 이동하여 3일간 동일 이상건 제외)', key=_key, value=check_value, on_change=skipToggleChange, args=(_key,))
                                                         
                                                        if st.session_state.skip_toggle_dict[_key] != on:
                                                            data = [(line_rev[img_path_sp[6]],img_path_sp[8],img_path_sp[6],img_path_sp[7],
                                                                        img_path_sp[9],img_path_sp[5],img_path_sp[10],img_path_sp[11],
                                                                        img_path_sp[12],img_path_sp[13].split('.')[0],st.session_state.user,datetime.now())]
                                                            # print(data)
                                                            if  on == False:
                                                                # print('on → off')
                                                                if DBDataDelete(data[0][0],data[0][2],data[0][1],data[0][4],data[0][7],data[0][8],data[0][9]):
                                                                    st.write('관리자 문의 필요')
            
                                                            elif on == True:
                                                                # print('off → on')
                                                                if DBDataUpLoad(data):
                                                                    st.write('관리자 문의 필요')
            
                                                        st.session_state.skip_toggle_dict[_key] = on
                                                        st.session_state.skip_toggle_dict_before[_key] = on
                                                    # # # # # # # # # # # # # #
                                                    
                                                    # if on:
                                                        # st.write(img_path)
                                                        # print(img_path[0])                                           
            
                                                    single_chart(img_path_result)
            
            
                                                    bt_key = key=f'butt_{grade}_{path_values}_{str(i)}_{st.session_state.last_filter}'
            
                                                    col1, col2, col3, col4 = st.columns(4)
            
            
                                                    with col1:
                                                        if st.button('동일성차트', bt_key):
                                                            if st.session_state.all_chart != bt_key:
                                                                    st.session_state.all_chart = bt_key
                                                            else:
                                                                st.session_state.all_chart = None
            
                                                            if st.session_state.output_type != bt_key+"matplotlib":
                                                                st.session_state.output_type = bt_key+"matplotlib"
                                                            else:
                                                                st.session_state.output_type = None            
                   
            
            
            
                                                    with col2:                                      
                                                        if st.button('변경점 리스트', bt_key+'_changepoint'):
                                                            if st.session_state.change_point != bt_key+'_changepoint':
                                                                st.session_state.change_point = bt_key+'_changepoint'
                                                            else:
                                                                st.session_state.change_point = None
            
                                                            if st.session_state.output_type != bt_key+"markdown":
                                                                st.session_state.output_type = bt_key+"markdown"
                                                            else:
                                                                st.session_state.output_type = None
            
            
                                                    with col3:
                                                        st.markdown('')
                                                    with col4:
                                                        st.markdown('')
            
            
                                                        
            
            
            
            
                                                    if st.session_state.output_type == bt_key+"matplotlib":
                                                        all_chart(img_path_result)
                                                    
                                                            
                                                    
                                                
                                                    elif st.session_state.output_type == bt_key+"markdown":
                                                        try:
                                                            for index, row in pd.read_parquet(img_path_result.replace('.png','.parquet')).iterrows():
                                                                st.markdown(f"[📘 {row['date']}  [{row['work_type']}] : {row['desc']}]({row['ctttm_url']})", unsafe_allow_html=True)
                                                        except:
                                                            st.markdown('😔 변경점 없음')
                                                              
            
                        # ===========================================Skip버튼 활성화 리스트 Drwing===================================================
                except Exception as E:
                    # print('no')
                    st.subheader("")
                    
            with tab3:
                st.subheader('동일성 분석')
                select_line = st.segmented_control(
                        "라인 선택",
                        ['H1L','15L','16L','17L','P1F','P1D','P23F','P2D','P3D','P3D2'], key='erd_comm_line'
                        )
                select_line_upload = select_line
           
                try:
                
                    selected_keys = [key for key, value in line_rev.items() if value == select_line] #선택한 라인 내 sdwt 리스트
                    select_sdwt = st.segmented_control("분임조 선택", selected_keys, key='erd_comm_sdwt')
            
                    base_path = Path('/appdata/abnormal_trend/pic/erd_commonality')
                    latest_date_folder = max(
                        (p for p in base_path.iterdir() if p.is_dir()),
                        key=lambda p: p.stat().st_mtime
                    )
            
                    url = f'{latest_date_folder}/{select_sdwt}'
            
                    
                    final_path = Path(f'{url}')
            
                    rows = []

                    if select_sdwt:
                        if list(final_path.rglob("img.png")) == []: st.markdown('이상건수가 없습니다')

                    # if img_path == None: st.markdown('이상건수가 없습니다')


# ===== END: fourth_question_section.py =====


# ===== START: fifth_question_section.py =====

# 모든 img 파일 탐색                    
for img_path in final_path.rglob("img.png"):
    relative_parts = img_path.relative_to(final_path).parts[:-1]
    rows.append(relative_parts)

# img 파일이 없는 경우 처리
if not rows:
    commonality_df = pd.DataFrame()
else:
    max_depth = max(len(r) for r in rows)
    columns = [chr(ord('A') + i) for i in range(max_depth)]
    rows = [list(r) + [None]*(max_depth-len(r)) for r in rows]
    commonality_df = pd.DataFrame(rows, columns=columns)

pattern = r"V_MFC_.*_Zero_MIN_T|V_Tunning_Gas.*_.*_MIN_T|V_STG_MFC_.*_Zero_MIN_T"

commonality_df = commonality_df[~commonality_df.apply(lambda row: row.astype(str).str.contains(pattern, regex=True)).any(axis=1)]

commonality_df = commonality_df.rename(columns={
    "A": "priority",
    "B": "step_seq",
    "C": "step_desc",
    "D": "ppid",
    "E": "recipe_id",
    "F": "sensor"
})

commonality_df[['sensor','ch_step']] = commonality_df['sensor'].str.extract(r'^(.*?_T)(_.*)$')

try:
    # =========================================================================================================
    step_cnt = list(commonality_df['step_desc'].unique())
    st.subheader("")
    st.subheader(f'조회결과 (총 이상step : {len(step_cnt)}개)', divider=True)

    if True:
        col1, col2 = st.columns([1.5, 2])
        with col1:
            with st.container(border=True):

                filtered_grade_table = commonality_df
                filtered_result_list = filtered_grade_table.values.tolist()

                filtered_grade_table_count = (
                    filtered_grade_table
                    .groupby('sensor')['step_desc']
                    .nunique()
                    .reset_index()
                )

                filtered_grade_table_count.columns = ['sensor', '이상step 건수']

                gb = GridOptionsBuilder.from_dataframe(filtered_grade_table_count)
                gb.configure_default_column(autoWidth=True)
                gb.configure_column("이상step 건수", width=120, sort="desc", sortable=True)
                gb.configure_column("sensor", filter=True)
                gb.configure_side_bar()
                gb.configure_pagination(enabled=True)
                gb.configure_selection('single')

                grid_options = gb.build()

                grid_response = AgGrid(
                    filtered_grade_table_count,
                    gridOptions=grid_options,
                    update_mode=GridUpdateMode.SELECTION_CHANGED,
                    height=400,
                    fit_columns_on_grid_load=True,
                    use_container_width=False,
                    key='commonality_table'
                )

                result = grid_response['selected_rows']
                select_sensor = result['sensor'][0]

        with st.container(border=True):
            if select_sensor:

                select_grade = ['A(c)','B(c)']

                history_data = (
                    select_line_upload,
                    select_sdwt,
                    json.dumps(select_grade),
                    select_sensor,
                    datetime.now(),
                    st.session_state.user
                )

                ClickedCategoryUpLoad(history_data)

                filtered_result_list = (
                    filtered_grade_table[
                        filtered_grade_table['sensor'] == select_sensor
                    ]
                )

                step_desc_list = list(filtered_result_list['step_desc'].unique())

                for step_description in step_desc_list:

                    final_img_drawing_table = (
                        filtered_result_list[
                            filtered_result_list['step_desc'] == step_description
                        ]
                    )

                    final_img_drawing_table['path'] = (
                        final_img_drawing_table.apply(
                            lambda x: str(Path(*x) / "img.png"),
                            axis=1
                        )
                    )

                    final_img_drawing_list = list(final_img_drawing_table['path'])

                    with st.expander(
                        f'{step_description} (이상 ch_step: {len(final_img_drawing_list)}개)',
                        expanded=False
                    ):
                        for img in final_img_drawing_list:
                            img_path = f'{url}/{img}'
                            img_path = re.sub(r'_T/', '_T', img_path)

                            with st.container(border=True):
                                st.image(img_path)

except Exception as E:
    st.subheader("")


# ===== END: fifth_question_section.py =====


# ===== START: hard_spec_tail_full_question.py =====

                                    how='left'  
                                ).with_columns(  
                                    pl.when(pl.col("BEGIN_STEP").str.contains(r"^\d+C\d+$"))  
                                      .then(pl.concat_str([pl.col("ch_step"), pl.lit("C"), pl.col("iter")]))  
                                      .otherwise(pl.col("ch_step"))  
                                      .alias("ch_step")  
                                ).filter(  
                                    ((pl.col('ch_step') >= pl.col('BEGIN_STEP')) & (pl.col('ch_step') <= pl.col('END_STEP')))  
                                    | (pl.col('ch_step') == 'ALL')  
                                ).sort(['PARAMETER_NAME', 'cycle', 'UPDATE_DATE']).unique(  
                                    subset=['PARAMETER_NAME', 'cycle'], keep='last'  
                                ).select(  
                                    ['PARAMETER_NAME', 'cycle', 'UPPER_VALUE', 'LOWER_VALUE']  
                                ).collect()
                            
                                # -------------------------------------------------  
                                # 컬럼명 변환: X, Y, Z, U 로 교체  
                                min_max_data = (  
                                    min_max_data  
                                    .join(  
                                        hard_spec.rename({'PARAMETER_NAME': 'sensor_name'}),  
                                        on=['sensor_name', 'cycle']  
                                    )  
                                    .rename({  
                                        'cycle'       : 'ch_step',  
                                        'UPPER_VALUE' : 'UPPER_HARD',  
                                        'LOWER_VALUE' : 'LOWER_HARD'  
                                    })  
                                    # ---- ★ X, Y, Z, U 로 컬럼명 변경 ★ ----  
                                    .rename({  
                                        'Lower_Spec' : '추천Spec(Lower)',   # Spec 하한  
                                        'Upper_Spec' : '추천Spec(Upper)',   # Spec 상한  
                                        'LOWER_HARD' : '기존Spec(Lower)',   # Hard 하한  
                                        'UPPER_HARD' : '기존Spec(Upper)'    # Hard 상한  
                                    })  
                                    .with_columns(  
                                        pl.col('추천Spec(Lower)').cast(pl.Float64),  
                                        pl.col('추천Spec(Upper)').cast(pl.Float64),  
                                        pl.col('기존Spec(Lower)').cast(pl.Float64),  
                                        pl.col('기존Spec(Upper)').cast(pl.Float64),  
                                    )  
                                    .with_columns(  
                                        (pl.col('기존Spec(Upper)') - pl.col('기존Spec(Lower)')).alias('HARD_gap'),  
                                        (pl.col('추천Spec(Upper)') - pl.col('추천Spec(Lower)')).alias('Reco_gap')  
                                    )  
                                    .with_columns(  
                                        (pl.col('HARD_gap') / pl.col('Reco_gap')).round(1).alias('ratio')  
                                    )  
                                    .with_columns(  
                                        pl.col('ratio').cast(pl.Utf8).alias('Spec격차')  
                                    )  
                                    .with_columns(  
                                        pl.when(pl.col("Spec격차") == 'inf')  
                                          .then(pl.lit("-배"))  
                                          .otherwise(pl.concat_str([pl.col("Spec격차"), pl.lit("배")]))  
                                          .alias('Spec격차'),  
                                        pl.when(pl.col("ratio").is_infinite())  
                                          .then(pl.lit(0))  
                                          .otherwise(pl.col("ratio"))  
                                          .alias("ratio")  
                                    )  
                                    .sort('ratio', descending=True)  
                                    .select(  
                                        ['priority', 'sensor_name', 'ch_step', '추천Spec(Lower)', '추천Spec(Upper)', '기존Spec(Lower)', '기존Spec(Upper)','Spec격차']  
                                    )  
                                    .filter(  
                                        pl.col('ch_step').str.contains(r'^\d+@(001|01)$')  
                                    )  
                                )          
                            except:
                                print(tb.format_exc())

                            st.markdown('예시 : ch_Step에서 @뒷 숫자는 iteration순번 표시 입니다.')
                            st.markdown('')
                            
                            st.session_state.min_max_data = min_max_data.to_pandas()


                        except Exception as E:
                            print('err')
                            print(E)
                            print(tb.format_exc())
                if st.session_state.min_max_data is None:
                    st.write('')

                else:
                    # 2️⃣ 표시용 데이터 생성 (여기서만 반올림)
                    df_original = st.session_state.min_max_data
                    df_display = df_original.copy()
                
                    cols = ['추천Spec(Lower)', '추천Spec(Upper)', '기존Spec(Lower)', '기존Spec(Upper)']
                    df_display[cols] = df_display[cols].apply(pd.to_numeric, errors='coerce').round(2)
                
                    # ⚠️ index 유지용 컬럼 추가 (매핑 안정성 확보)
                    df_display = df_display.reset_index(drop=False)
                
                    # 3️⃣ 엑셀 다운로드는 원본 기준 (선택사항)
                    output = BytesIO()
                    df_original.to_excel(output, index=False)
                    st.download_button(
                        "엑셀 다운로드",
                        data=output.getvalue(),
                        file_name="data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        icon=":material/download:"
                    )
                
                    # 4️⃣ Grid 구성 (표시용 데이터 사용)
                    gb = GridOptionsBuilder.from_dataframe(df_display)
                
                    gb.configure_default_column(sortable=True)
                
                    gb.configure_selection(
                        selection_mode="multiple",
                        use_checkbox=True
                    )
                
                    gb.configure_grid_options(multiSortKey="shift")
                
                    grid_options = gb.build()
                
                    grid_response = AgGrid(
                        df_display,  # 👉 표시용 데이터
                        gridOptions=grid_options,
                        update_mode="SELECTION_CHANGED",
                        key="min_max_grid",
                        height=1000
                    )
                
                    # 5️⃣ 선택된 row → 원본 데이터로 매핑
                    if grid_response["selected_rows"] is not None:
                        selected_display = grid_response["selected_rows"]
                
                        # 👉 index 기준으로 원본에서 조회
                        selected = df_original.loc[selected_display['index']].head(15)
                    else:
                        selected = None
                
                    st.session_state.select_min_max_data = selected
                   
                    st.write("선택된 센서(그래프 그리기는 최대 15개 데이터에 대해서만 그려집니다.)", selected)
                    
                visual_hard_spec = st.checkbox("Hard Spec표시 제거 (Y축 Scale 때문에 Trend가 일자로 보일 시 체크 후 '그래프 그리기' 클릭)")
                if visual_hard_spec: hard_vi = 1
                else: hard_vi = 0
                
                if st.button("그래프 그리기"):
                    # print(st.session_state.user)
                    if st.session_state.user == '_': # if st.session_state.user != 't1232.kang':
                        st.write('개발 중')
                    else:
                        print('*'*30)
                        #print( st.session_state.select_min_max_data[['sensor_name','ch_step']].values )
                        #print('* conditions', st.session_state.hard_spec_search_condition)
                        files = str(st.session_state.hard_spec_search_condition)
                        json_SENSOR = json.dumps(st.session_state.select_min_max_data[['sensor_name','ch_step']].values.tolist())
                        safe_json_SENSOR = shlex.quote(json_SENSOR)
                        
                        temp = str(uuid.uuid4()).replace("-", "")
                        LOCAL_DIR = f'/appdata/abnormal_trend/pic/erd_hard_spec/{temp}'
                        SERVER_LOCAL_DIR = f'/appdata/abnormal_trend/pic_server2/erd_hard_spec/{temp}'
                        # print('safe_json_SENSOR', safe_json_SENSOR)
                        
                        if os.path.exists(LOCAL_DIR): shutil.rmtree(LOCAL_DIR)
                        os.makedirs(LOCAL_DIR, exist_ok=True)
                        current_mode = os.stat(LOCAL_DIR).st_mode & 0o777
                        if current_mode != 0o777: os.chmod(LOCAL_DIR, 0o777)
                        
                        today = datetime.today()
                        start_date = today - timedelta(days=120)
                        
                        for con in st.session_state.hard_spec_search_condition:
                            line_id, step_seq, ppid, rcp = con
                        
                            BASE_DIR = f'/appdata/m_erdtsum_data_agg/{line_id}/{step_seq}'
                            hdfs_files = [f'{BASE_DIR}/{i}' for i in st.session_state.hdfs_client.list(BASE_DIR) \
                                        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", i) \
                                       and start_date <= datetime.strptime(i, "%Y-%m-%d") <= today]
                            # print('dates', dates)
                            
                            ssh = None
                            try:
                                ssh = paramiko.SSHClient()
                                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                                ssh.connect(HDFS_HOST, username=HDFS_NAME, password=HDFS_PASSWORD)
                                command = f"source /home/hadoop/hadoop_env/bin/activate && python3 /appdata/abnormal_trend/pic_server2/call_hard_spec_data.py \"{hdfs_files}\" \"{SERVER_LOCAL_DIR}\" \"{ppid}\" \"{rcp}\" {safe_json_SENSOR} "
                                stdin, stdout, stderr = ssh.exec_command( command )
                                #print("stdout:", stdout.read().decode())
                                #print("stderr:", stderr.read().decode())
                                stdout.read().decode()
                                stderr.read().decode()
                            finally:
                                if ssh is not None:
                                    ssh.close()
                        
                        data = pl.scan_parquet( LOCAL_DIR ).with_columns(pl.col('param_value').cast(pl.Float32).alias('param_value'))

                        for iter_row in st.session_state.select_min_max_data.values:
                            _, sensor, ch_step, cl, cu, hl, hu, _ = iter_row
                            ch_step = ch_step.split('@')[0]
                            data_for_all_chart = \
                            data.filter(
                                (pl.col('param_name') == sensor)
                                & (pl.col('ch_step') == ch_step)
                            )

                            all_chart_hard_spec(data_for_all_chart, sensor, ch_step, cl, cu, hl, hu, hard_vi)
                        
                        try:
                            shutil.rmtree(LOCAL_DIR)
                        except:
                            pass

                                                            # st.write(img_path_result)
                                                           


                                                        elif st.session_state.output_type == bt_key+"plotly":
                                                            start = datetime.now()
                                                            sp = img_path_result.split('/')
                                                            folder_path = '/'+'/'.join(sp[1:-1])
                                                            file_path =  folder_path + '/data.parquet'
                                                            eqp_ch = sp[-1].split('.')[0]

                                                            img_data = pd.read_parquet(file_path)
                                                            if 'eqp_cb' in img_data.columns: img_data.drop(columns=['eqp_cb'], inplace=True)
                                                            drawing_df = img_data[(img_data['eqp_id']==eqp_ch.split('-')[0])&(img_data['disp_name']==eqp_ch.split('-')[1])]
                                                            fig = px.scatter(
                                                                                drawing_df,
                                                                                x="act_time",
                                                                                y=img_data.columns[-1],
                                                                                hover_data=[img_data.columns[-1],'root_lot_id','wafer_id']
                                                                                )

                                                            fig.update_layout(width=400, height=300)
                                                            st.plotly_chart(fig, use_container_width=True)

                                # ============================    Skip버튼 미설정 Drwing      =============================================






                                # ===========================================================================================================================

                                for_enu_true = st.session_state.common_history[common_grade][st.session_state.common_history[common_grade]['check'] == True]
                                #print(for_enu_true[['file_path','check']].values)
                                #skip체크있는 최종 이상감지 리스트(file_path_df)에 선택한 센서, skip유무, eqp까지 필터 후 변수에 저장 (for문에 직접 넣으려니 너무 길어서....)
                                with st.expander(f'Skip 리스트 ({len(for_enu_true)} 건)', expanded=False):

                                    with st.container(border=True):
                                        cols = st.columns(2)
                                        for i, path_values in enumerate(for_enu_true[['file_path','comment','knox_id','check']].values):
                                            img_path = path_values[0]
                                            img_path_sp = img_path.split('/')
                                            img_path_comment = path_values[1]
                                            img_path_knoxid = path_values[2]

                                            with cols[i % 2]:
                                                with st.container(border=True):
                                                    img_path_result = img_path.replace('pic_server2', 'pic')
                                                    st.markdown(img_path_sp[6] + ' / ' + img_path_sp[7] + ' / ' + img_path_sp[8] + ' / ' + img_path_sp[9] + ' / ' + img_path_sp[10] + ' / ' + img_path_sp[-1].split('.')[0])
                                                    st.markdown(f'skip사유 (등록자) : {img_path_comment} / {img_path_knoxid}')

                                                    ###########################
                                                    # toggle dict 데이터 확인 #
                                                    ###########################

                                                    _key=f'skip_toggle_{str(common_grade)}_{str(i)}_{path_values}_{st.session_state.common_last_filter}'

                                                    if _key not in st.session_state.common_skip_toggle_dict:
                                                        check_value = path_values[1]
                                                        st.session_state.common_skip_toggle_dict_before[_key] = check_value
                                                        common_on = st.toggle('Skip (Skip 리스트로 이동하여 3일간 동일 이상건 제외)', key=_key, value=check_value, on_change=commonSkipToggleChange, args=(_key,))
                                                        st.session_state.common_skip_toggle_dict[_key] = check_value
                                                    else:
                                                        check_value = st.session_state.common_skip_toggle_dict_before[_key]
                                                        common_on = st.toggle('Skip (Skip 리스트로 이동하여 3일간 동일 이상건 제외)', key=_key, value=check_value, on_change=commonSkipToggleChange, args=(_key,))

                                                        if st.session_state.skip_toggle_dict[_key] != common_on:
                                                            data = [('-','-',img_path_sp[6],img_path_sp[7],
                                                                        '-',img_path_sp[5],img_path_sp[8],img_path_sp[9],
                                                                        img_path_sp[10],img_path_sp[11].split('.')[0],st.session_state.user,datetime.now())]
                                                            # print(data)
                                                            if  common_on == False:
                                                                # print('on → off')
                                                                data = data[0]
                                                                if DBDataDelete(data[0],data[1],data[2],data[4],data[7],data[8],data[9]):
                                                                    st.write('관리자 문의 필요')

                                                            elif common_on == True:
                                                                # print('off → on')
                                                                if DBDataUpLoad(data):
                                                                    st.write('관리자 문의 필요')

                                                        st.session_state.common_skip_toggle_dict[_key] = common_on
                                                        st.session_state.common_skip_toggle_dict_before[_key] = common_on
                                                    # # # # # # # # # # # # # #

                                                    # if on:
                                                        # st.write(img_path)
                                                        # print(img_path[0]) 
                                                    st.image(img_path_result)


                                                    bt_key = key=f'butt_{common_grade}_{path_values}_{str(i)}_{st.session_state.common_last_filter}'

                                                    col1, col2, col4, col5 = st.columns(4)


                                                    with col1:                                                
                                                        if st.button('동일성차트', bt_key):
                                                            if st.session_state.all_chart != bt_key:
                                                                    st.session_state.all_chart = bt_key
                                                            else:
                                                                st.session_state.all_chart = None

                                                            if st.session_state.output_type != bt_key+"matplotlib":
                                                                st.session_state.output_type = bt_key+"matplotlib"
                                                            else:
                                                                st.session_state.output_type = None



                                                    with col2:
                                                        if st.button('자설비 Chart', bt_key+'_single_chart'):                                               
                                                            if st.session_state.single_chart != bt_key+'_single_chart':
                                                                st.session_state.single_chart = bt_key+'_single_chart'
                                                            else:
                                                                st.session_state.single_chart = None

                                                            if st.session_state.output_type != bt_key+"plotly":
                                                                st.session_state.output_type = bt_key+"plotly"
                                                            else:
                                                                st.session_state.output_type = None



                                                    with col4:
                                                        st.markdown('')
                                                    with col5:
                                                        st.markdown('')


                                                    if st.session_state.output_type == bt_key+"matplotlib":
                                                        all_chart(img_path_result)



                                                    elif st.session_state.output_type == bt_key+"plotly":
                                                        start = datetime.now()
                                                        sp = img_path_result.split('/')
                                                        folder_path = '/'+'/'.join(sp[1:-1])
                                                        file_path =  folder_path + '/data.parquet'
                                                        eqp_ch = sp[-1].split('.')[0]

                                                        img_data = pd.read_parquet(file_path)
                                                        if 'eqp_cb' in img_data.columns: img_data.drop(columns=['eqp_cb'], inplace=True)
                                                        drawing_df = img_data[(img_data['eqp_id']==eqp_ch.split('-')[0])&(img_data['disp_name']==eqp_ch.split('-')[1])]
                                                        fig = px.scatter(
                                                                            drawing_df,
                                                                            x="act_time",
                                                                            y=img_data.columns[-1],
                                                                            hover_data=[img_data.columns[-1],'root_lot_id','wafer_id']
                                                                            )

                                                        fig.update_layout(width=400, height=300)
                                                        st.plotly_chart(fig, use_container_width=True)



                                                    elif st.session_state.output_type == bt_key+"markdown":
                                                        try:
                                                            for index, row in pd.read_parquet(img_path_result.replace('.png','.parquet')).iterrows():
                                                                st.markdown(f"[📘 {row['date']}  [{row['work_type']}] : {row['desc']}]({row['ctttm_url']})", unsafe_allow_html=True)
                                                        except:
                                                            st.markdown('😔 변경점 없음')


                        # ===========================================Skip버튼 활성화 리스트 Drwing===================================================
                except Exception as E:
                    # print('no')
                    st.subheader("")
            # =======================================================================================================================================
            # ============================
            
            
            
            
            with tab5:
                hit_data = HitDBDataLoad()
                hit_data['line_rev'] = hit_data['sdwt'].map(line_rev)
                
                with st.container(border=True):
                    try:
                        select_line = st.segmented_control(
                            "라인 선택",
                            hit_data['line_rev'].unique(), key='line_hit'
                            )
            
            
                        select_sdwt = st.segmented_control(
                            "분임조 선택",
                            hit_data[hit_data['line_rev']==select_line]['sdwt'].unique(), key='sdwt_hit'
                            )
            
                        if select_sdwt:
                            hit_total_data = hit_data[(hit_data['line_rev']==select_line)&(hit_data['sdwt']==select_sdwt)]
                            st.subheader(f'조회결과 (총{len(hit_total_data)}건)', divider=True)
            
                            for date_list in hit_total_data['update_date'].unique():
                                final_hit_total_data = hit_total_data[hit_total_data['update_date'] == date_list]
                                with st.expander(f'{date_list} ({len(final_hit_total_data)}건)', expanded=False):
                                    with st.container(border=True):   
                                        cols = st.columns(2)
                                        for i, path_values in enumerate(final_hit_total_data.values):
                                            if 'erd' in path_values[3]:
                                                img_path = path_values[3] #차트 drwing위한 이미지 경로 변수 저장

                                            else: 
                                                img_path = path_values[3]
                                                                                        

                                            
                                            img_path_sp = img_path.split('/') #차트에 각종 정보 표현위해 '/'구분자로 쪼개어 경로정보 list에 저장
                                            with cols[i % 2]:
                                                with st.container(border=True):
                                                    st.markdown(img_path_sp[6] + ' / ' + img_path_sp[7] + ' / ' + img_path_sp[8] + ' / ' + img_path_sp[-1].split('.')[0])                    
                                                    try:
                                                        single_chart(img_path)
                                                    except:
                                                        pass
            
                                                    col1, col2, col3, col4, col5 = st.columns(5)
            
                                                    with col1:
                                                        
                                                        _key = f'{i}_{select_line}_{select_sdwt}_{img_path}' 
            
                                                        if st.button('삭제', key = _key+'button'):
                                                            st.session_state.hit_del = _key+'pills'
                                                            
                                                        if st.session_state.hit_del == _key+'pills':
                                                            selection = st.pills('삭제하시겠습니까?', ['YES','NO '],key = _key+'pills')
                                                            if selection == 'YES':
                                                                HitDBDataDelete(img_path)
                                                                st.markdown('삭제완료')
            
                                                            
                                                    with col2:
                                                        st.markdown('')
                                                    with col3:
                                                        st.markdown('')
                                                    with col4:
                                                        st.markdown('')
                                                    with col5:
                                                        st.markdown('')                                               
            
            
                    except TypeError:
                        pass
            
            with tab6:
                st.image('/appdata/abnormal_trend/code/manual.png')

            with tab7:
                st.header('Hard Spec 추천 조회')
                st.markdown('')
                
                col1, col2 = st.columns(2)
                with col1:
                    with st.expander('로직 설명', expanded=False):
                        with st.container(border=False):
                            st.image('/appdata/abnormal_trend/pic/recommand_spec.png')
                
                st.markdown('')
                st.markdown('')

                col1, col2, col3, col4 = st.columns(4)

                # line_list = ['KFBC', 'KFBE', 'KFBG', 'KFBH', 'KFBJ', 'KFE3', 'KFE5', 'KFHB', 'KFHG', 'KFJB', 'PFB3', 'PFB4', 'PFBB', 'PFBP', 'PFPB', 'XFB1', 'XFB2']
                try:
                    with col1:
                        line_ids = st.selectbox("라인ID 선택해주세요", 
                                        (['H1L','15L','16L','17L','P1F','P1D','P23F','P2D','P3D','P3D2']),
                                               )
                        if line_ids:
                            try:
                                models = st.session_state.hdfs_client.list(f'/appdata/erd_stats_commonality/{line_ids}')
                                step_model_dict = defaultdict(list)
                                ver_step_dict = defaultdict(list)
                                for model in models:
                                    steps = st.session_state.hdfs_client.list(f'/appdata/erd_stats_commonality/{line_ids}/{model}')
                                    for step in steps:
                                        step_model_dict[step].append(model)
                                        ver_step_dict[step[0]+'%'+step[2:]].append(step)

                                # steps = sorted(list(set(step_model_dict.keys())))
                                # step_seq_select = steps
                                step_seq_select = sorted([i for i in ver_step_dict.keys()])
                            except:
                                step_seq_select = ()
                        else:
                            step_seq_select = ()

                    with col2:
                        step_seq = st.selectbox("step_seq 선택해주세요", 
                                                (step_seq_select), index=None, placeholder='Select')

                        if step_seq:
                            select_steps = ver_step_dict[step_seq]
                            ppids = set()
                            select_groups = []
                            eqp_models = set()
                            for select_step in select_steps:
                                models = step_model_dict[select_step]
                                eqp_models.update(models)
                                for model in models:
                                    # ppids.update(set(st.session_state.hdfs_client.list(f'/appdata/erd_stats_commonality/{line_ids}/{model}/{step_seq}')))
                                    _hdfs_file_path = f'/appdata/erd_stats_commonality/{line_ids}/{model}/{select_step}'
                                    _ppids = st.session_state.hdfs_client.list(_hdfs_file_path)
                                    ppids.update(set(_ppids))
                                    select_groups += [f'{_hdfs_file_path}/{i}' for i in _ppids]
                            
                            recipe_lists = []
                            recipe_ids = set()
                            for _file in select_groups:
                                _rcps = st.session_state.hdfs_client.list(_file)
                                recipe_ids.update(set(_rcps))
                                recipe_lists += [f'{_file}/{i}'for i in _rcps if i != '-']
                            
                            # ppids = sorted(list(ppids))
                        else:
                            recipe_ids = ()
                             

                    with col3:
                        recipe_id = st.selectbox("RecipeID 선택해주세요", 
                                                (recipe_ids) ,index=None ,placeholder='Select')
                        if recipe_id:
                            
                            sql = f'''
                            SELECT DISTINCT fdc_model
                            FROM edisn.step_eqp_info
                            WHERE step_seq like '{step_seq}'
                              AND eqp_model in {tuple(eqp_models)}
                            '''.replace(',)',')')
                            with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                                with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                                    cursor.execute(sql)
                                    fdc_models = [i['fdc_model'] for i in cursor.fetchall()]
                            # print('recipe_id', [i for i in recipe_lists if i.endswith(recipe_id)])
                        else:
                            fdc_models = ()
                    
                    with col4:
                        fdc_model = st.selectbox("FDC Model 선택해주세요", 
                                                (fdc_models) ,index=None ,placeholder='Select')
                        
                        if fdc_model:
                            check_hdfs_list = True
                        else:
                            check_hdfs_list = False
                    
                    #with col4:
                    #    recipe_id = st.selectbox("RecipeID 선택해주세요", 
                    #                            (recipe_ids) ,index=None, placeholder='Select')
                except TypeError:
                        pass

                if st.button("추천SPEC 조회"):
                    st.session_state.min_max_data = None
                    st.session_state.hard_spec_search_condition = None
                    # print('conditions:',st.session_state.hard_spec_search_condition)
                    history_data = ('SPEC', line_ids, step_seq, recipe_id, datetime.now(), st.session_state.user)
                    ClickedCategoryUpLoad(history_data)
                    if check_hdfs_list:
                        st.session_state.hard_spec_search_condition = (line_ids, step_seq, recipe_id)
                        try:
                            datas = []

                            for hdfs_path_dir in [i for i in recipe_lists if i.split('/')[-1] == recipe_id]:

                                try:
                                    iss = st.session_state.hdfs_client.list(hdfs_path_dir)
                                    for i in iss:
                                        datas.append( f'{hdfs_path_dir}/{i}' )
                                except:
                                    pass

                            _path_data = []
                            for _data in datas:
                                _path_data.append((*_data.split('/')[3:], _data))
                            
                            files =                             pl.DataFrame(
                                _path_data, schema=['line','model','step','ppid','rcp','date','path'], orient='row'
                            ).sort(
                                'date', descending=True
                            ).group_by(
                                ['line','model','step','ppid','rcp']
                            ).agg(
                                pl.col('path').head(120)
                            ).explode(
                                "path"
                            )
                            print('*'*20)
                            st.session_state.hard_spec_search_condition = files.select(['line','step','ppid','rcp']).unique().rows()
                            # print(files.select(['line','step','ppid','rcp']).unique().rows())
                            print('*'*20)
                            files = files['path'].to_list()
                            
                            # files = sorted(list(datas))[-120:]

                            local_path = f'/appdata/abnormal_trend/pic/temp_all_stats/{st.session_state.user_uuid}'
                            os.makedirs(local_path, exist_ok=True)

                            for file in files:
                                hdfs_path = file # f'{hdfs_path_dir}/{file}'
                                try:
                                    st.session_state.hdfs_client.download(hdfs_path, local_path, overwrite=True)
                                except:
                                    pass
                                
                            #lf = pl.scan_parquet( local_path ).filter(pl.col('value').is_not_null())
                            lf = pl.scan_parquet( local_path )
                     
                            min_max_data =                             lf.group_by(
                                ['sensor']
                            ).agg(
                                pl.col('upper_bound').max().alias('max'),
                                pl.col('lower_bound').min().alias('min'),
                            ).with_columns(
                                ((pl.col('max')-pl.col('min'))*0.05).alias('gap')
                            ).with_columns(
                                (pl.col('max')+pl.col('gap')).alias('max'),
                                (pl.col('min')-pl.col('gap')).alias('min')
                            ).select(
                                ['sensor','max','min']
                            ).with_columns(
                                pl.col("sensor")
                                .map_elements(lambda x: {
                                    "col1": split_by_reverse(x)[0],
                                    "col2": split_by_reverse(x)[1],
                                 })
                                .alias("split")
                            ).unnest("split").collect()
                            # ===========================================================================================
                            
                            min_max_data =                             min_max_data.rename(
                                {'col1':'sensor_name', 'col2':'cycle'}
                            ).select(
                                ['sensor_name','cycle','min','max']
                            )

                            shutil.rmtree(local_path)

                            AB_sensors = pl.read_parquet(  
                                '/appdata/abnormal_trend/pic/priority/priority.parquet'  
                            ).filter(  
                                pl.col('eqp_id') == fdc_model
                            ).filter(  
                                pl.col('priority').is_in(['A','B'])  
                            ).select(  
                                ['param_name','priority']  
                            ).sort(  
                                ['param_name','priority']  
                            ).unique(subset=['param_name'], keep='first')
                            
                            # -------------------------------------------------  
                            # min_max_data 전처리  
                            min_max_data = min_max_data.rename({  
                                "min": "Lower_Spec",  
                                "max": "Upper_Spec"  
                            }).join(  
                                AB_sensors.rename({'param_name': 'sensor_name'}),  
                                on=['sensor_name'],  
                                how='left'  
                            ).filter(  
                                pl.col('priority').is_in(['A','B'])  
                            ).sort(['priority', 'sensor_name'])
                            
                            # -------------------------------------------------  
                            # Hard Spec 로드  
                            try:  
                                unit_model_ids = pl.scan_parquet(  
                                    '/appdata/abnormal_trend/pic/unit_model.parquet'  
                                ).filter(  
                                    pl.col('fdc_model') == fdc_model  
                                ).collect()['unit_model_id'].unique()
                            
                                hard_spec = pl.scan_parquet(  
                                    '/appdata/abnormal_trend/pic/HARD_LIMIT.parquet'  
                                ).filter(  
                                    pl.col('UNIT_MODEL_ID').is_in(unit_model_ids)  
                                ).filter(  
                                    (pl.col('PARAMETER_NAME').is_in(min_max_data['sensor_name'].unique()))  
                                    & (pl.col('RECIPE') == recipe_id)  
                                ).sort(['PARAMETER_NAME', 'UPDATE_DATE']).join(  
                                    min_max_data.rename({'sensor_name': 'PARAMETER_NAME'}).with_columns(  
                                        pl.col("cycle")  
                                        .str.split("@")  
                                        .list.to_struct(fields=["ch_step", "iter"])  
                                        .alias("tmp")  
                                    ).unnest("tmp").with_columns(  
                                        pl.col('iter').cast(pl.Int8)  
                                    ).with_columns(  
                                        pl.col('iter').cast(pl.Utf8)  
                                    ).lazy(),  
                                    on=['PARAMETER_NAME'],  


# ===== END: plotly_to_hard_spec_section.py =====


# ===== START: third_question_section.py =====

                    if span <= 0:
                        span = 1.0
                        duration = pd.to_timedelta(span, unit="s")
                
                    gap = span * gap_ratio
                
                    # --- composite x 생성: offset + (act_time - 전역 tmin) ---
                    i = df[eqp_col].map(eqp_to_i)
                    
                    # 혹시 mapping 안 된 값이 있으면 제거
                    df = df[i.notna()].copy()
                    i = i[i.notna()].astype(int).to_numpy()
                
                    offset = i * (span + gap)
                    within = (df[time_col] - tmin).dt.total_seconds().to_numpy()
                    df["_x_comp"] = offset + within
                    # idx = temp.index
                    # --- color list 생성 ---
                    if not mode: c = 'gray'
                    else: c = 'blue'
                    colors = np.array([ c ]*len(df))
                    if not mode:
                        colors[df[df[eqp_col]==eqp_id].index] = 'red'
                    
                    # --- 전체 x폭(✅ (2) 좌우 여백 제거용 range) ---
                    nseg = len(eqps)
                    x0_full = 0.0
                    x1_full = (nseg - 1) * (span + gap) + span
                    
                    # -----------------------------
                    # ✅ 하단 x축 tick: 구간별 20/50/80% 3개만 + YYYY-MM-DD
                    # -----------------------------
                    tickvals = []
                    ticktext = []
                    for k in range(len(eqps)):
                        seg_start = k * (span + gap)
                        for frac in tick_fracs:
                            x = seg_start + span * frac
                            tt = tmin + pd.to_timedelta(span * frac, unit="s")
                            tickvals.append(x)
                            ticktext.append(tt.strftime("%Y-%m-%d"))  # ✅ 날짜까지만
                    # --- figure ---
                    fig = go.Figure()
                    try:
                        if not mode:
                            fig.add_trace(
                                go.Scattergl(
                                    x=df["_x_comp"],
                                    y=df[value_col],
                                    mode="markers",
                                    marker=dict(
                                        size=marker_size,
                                        color=colors
                                    ),
                                    customdata=np.stack(
                                        [df[eqp_col].astype(str), df[time_col].dt.strftime("%Y-%m-%d %H:%M:%S"), df[lot_col]],
                                        axis=1
                                    ),
                                    hovertemplate=(
                                        "eqp=%{customdata[0]}<br>"
                                        "act_time=%{customdata[1]}<br>"
                                        "lot=%{customdata[2]}<br>"
                                        f"{value_col}=%{{y}}<extra></extra>"
                                    ),
                                    showlegend=False
                                )
                            )
                        else:
                            fig.add_trace(
                                go.Scattergl(
                                    x=df["_x_comp"],
                                    y=df[value_col],
                                    mode="markers",
                                    marker=dict(
                                        size=marker_size,
                                        color=colors
                                    ),
                                    showlegend=False
                                )
                            )
                            for ss in min_max_data:
                                fig.add_hline(
                                    y=ss,                 # 기준값
                                    line_width=1,
                                    line_dash="dash",
                                    line_color="orange",
                                    opacity=0.8
                                )
                            
                    except Exception as E: print(E)
                    # --- 배경 음영 + 경계선 ---
                    for k in range(len(eqps)):
                        seg_start = k * (span + gap)
                        seg_end = seg_start + span
                
                        if k % 2 == 0:
                            fig.add_vrect(x0=seg_start, x1=seg_end, opacity=0.06, line_width=0)
                
                        if k < len(eqps) - 1:
                            boundary = seg_end + (gap / 2 if gap > 0 else 0)
                            fig.add_vline(x=boundary, line_width=0.5, line_dash="dot", opacity=0.6)
                
                    # -----------------------------
                    # ✅ (1) EQP 라벨을 "각 구간 상단"에 annotation으로 확실히 표시
                    #   - 반시계 90도: textangle=90
                    #   - 아래→위 방향으로 읽힘
                    # -----------------------------
                    for k, e in enumerate(eqps):
                        x_center = k * (span + gap) + span / 2
                        if not mode:
                            if e == eqp_id: color = 'red'
                            else: color = 'gray'
                        else:
                            color = 'blue'
                        fig.add_annotation(
                            x=x_center,
                            y=0.995, # y=0.8                 # 상단(페이퍼 좌표)
                            xref="x",
                            yref="paper",
                            text=str(e),
                            showarrow=False,
                            textangle=270,           # ✅ 반시계 90도 (세로, 아래->위)
                            xanchor="center",
                            yanchor="top", # yanchor="bottom",
                            yshift=-2,          # 살짝 아래로(픽셀) 내려서 경계에 붙는 느낌 완화
                            align="center",
                            font=dict(
                                size=10,
                                color=color,
                                family='Arial'
                            )
                        )
                    # --- 축 세팅 ---
                    fig.update_xaxes(
                        tickmode="array",
                        tickvals=tickvals,
                        ticktext=ticktext,
                        range=[x0_full, x1_full],      # ✅ (2)
                        showticklabels=(not hide_xticks_until_zoom),
                        ticks=("outside" if not hide_xticks_until_zoom else ""),
                        ticklen=(5 if not hide_xticks_until_zoom else 0),
                    )
                    fig.update_yaxes(title=value_col)
                
                    fig.update_layout(
                        height=650,
                        margin=dict(t=170),   # ✅ 상단 세로 라벨 공간 (라벨 길면 더 키워도 됨)
                        hovermode="closest",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
            # ======================= 동일성 Chart Drawing 함수 지정 ======================================================================
            
            
            def all_chart_hard_spec(data_for_all_chart, sensor, ch_step, cl, cu, hl, hu, hard_vi):
                start = datetime.now()

                result = data_for_all_chart.select([
                                                pl.col('act_time').min().alias('time_min'),
                                                pl.col('act_time').max().alias('time_max')
                                            ]).collect()
                eqp_cb_unique = [i for i in data_for_all_chart.select(['eqp_id','disp_name']) \
                                              .unique() \
                                              .sort(['eqp_id','disp_name']).collect().iter_rows()]


                fig = plt.figure(figsize=(12,5))

                cmap = plt.get_cmap('tab20c', len(eqp_cb_unique))
                gs = GridSpec(1, len(eqp_cb_unique), figure=fig)
                ax_list = []

                for n1, ec1 in enumerate( eqp_cb_unique ):
                    if n1 == 0:
                        ax_list.append( fig.add_subplot(gs[0,n1]) )
                    else:
                        ax_list.append( fig.add_subplot(gs[0,n1], sharey=ax_list[0]) )
                        ax_list[n1].tick_params(axis='y', which='both', left=False, labelleft=False)

                    full_range = pd.date_range(start=result['time_min'][0], end=result['time_max'][0])

                    ax_list[n1].text(0.05,0.98, '-'.join(ec1), transform=ax_list[n1].transAxes, verticalalignment='top', horizontalalignment='left', fontsize=9, rotation=90)
                    ax_list[n1].set_xlim([full_range.min(), full_range.max()])


                    mid_value = full_range[round(len(full_range)/2)]
                    ticks = [ mid_value , full_range.max() + pd.Timedelta(hours=240) ]

                    ax_list[n1].set_xticks(ticks)
                    ax_list[n1].set_xticklabels([ mid_value.strftime('%Y-%m-%d') , full_range.max().strftime('%Y-%m-%d') ], rotation=90, fontsize=8)
                #target_eqp = None
                for n2, ec2 in enumerate( eqp_cb_unique ):
                    color = cmap(n2%10+n2%10)
                    t = data_for_all_chart.filter(
                        pl.col('eqp_id')==ec2[0],
                        pl.col('disp_name')==ec2[1]
                    ).drop_nulls().collect()

                    ax_list[n2].scatter(t['act_time'],t['param_value'], color=color, s= 25, edgecolors='k', linewidths=0.05)

                    if hard_vi == 0:
                        for s in [cu, cl]:
                            ax_list[n2].axhline(y=float(s), linestyle='--', color='red')
                        for s in [hu, hl]:
                            ax_list[n2].axhline(y=float(s), linestyle='--', color='blue')
                    elif hard_vi == 1:
                        for s in [cu, cl]:
                            ax_list[n2].axhline(y=float(s), linestyle='--', color='red')
                    #if select_eqp == list(ec2):
                    #    target_eqp = n2
                        # 각 축의 테두리를 빨갛게 설정

                    ax_list[n2].yaxis.grid(True, linestyle='--', linewidth=0.7)

                #for spine in ax_list[target_eqp].spines.values():
                #    spine.set_edgecolor('red')
                #    spine.set_linewidth(1)  # 테두리 두께 조정

                plt.subplots_adjust(wspace=.05)
                suptitle = sensor+' - '+ch_step
                plt.suptitle(suptitle)
                # st.write(f'end: {datetime.now()-start}')
                st.pyplot(fig)
            
            # ======================= step all 선택하면 나머지 해제  =====
            def updateStepSelect():
                if 'ALL' in st.session_state.selected_step_button:
                    st.session_state.selected_step_button = 'ALL'
            
            
            def updateVerSelect():
                if 'ALL' in st.session_state.selected_ver_button:
                    st.session_state.selected_ver_button = 'ALL'
            
            # 251109 추가 ========
            def commonUpdateStepSelect():
                if 'ALL' in st.session_state.common_selected_step_button:
                    st.session_state.common_selected_step_button = 'ALL'


            def commonUpdateVerSelect():
                if 'ALL' in st.session_state.common_selected_ver_button:
                    st.session_state.common_selected_ver_button = 'ALL'
            # ====================
            
            # =========================================================================================================

                            
                    
            with tab8:
                st.header('P1F 수율 기반 FDC Spec 추천')
                st.markdown('')

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    step_seq = st.selectbox("Step seq 를 선택해주세요.", 
                                            ('CR380250','CR580250','CR590180','CR610200','CU380250', 'CU580250','CU590180','CU610200'),
                                           )
                    if step_seq:
                        paths = [i for i in glob.glob('/appdata/abnormal_trend/pic/yh/P1F_CHH/*') if step_seq in i]
                        for path in paths:
                            ppid = path.split('/')[-1].split('_')[1]
                    else:
                        ppid = ''
                
                with col2:
                    recipeid = st.selectbox('Recipe id',
                                 (ppid)
                                )
                    
                col5, col6 = st.columns(2)
                with col5:
                    with st.expander('로직 설명', expanded=False):
                        st.markdown('아래는 설명을 위한 예시입니다. ')
                        st.markdown('수율 상위 50% 와 하위 50% 를 기준으로 wafer 를 grouping 하여 확률밀도분포를 그렸을 때,')
                        st.markdown('하위 50% 의 물량들의 fdc data 분포가 더 큰 fdc_parameter 들만 추출하여')
                        st.markdown('수율 상위 50% 그룹의 outlier 제외한 min max spec 입니다.')
                        with st.container(border=False):
                            st.image('/appdata/abnormal_trend/pic/yh/P1F_CHH/yh_desc.png')
                        
                if st.button("조회"):
                    history_data = ('SPEC(Y)', 'P1F', step_seq, recipeid, datetime.now(), st.session_state.user)
                    ClickedCategoryUpLoad(history_data)
                    if step_seq:
                        #st.markdown('수율 기준 상위 50%를 물량과 하위 50% 물량의 FDC ERD 분포를 비교하여')
                        #st.markdown('하위 50% Spec 분포가 넓은 파라미터들에 대한 상위 50% 물량의 FDC Min Max 를 제안합니다.')
                        st.markdown('g_min, g_max : 수율 상위 50% 물량의 MIN MAX')
                        st.markdown('b_min, b_max : 수율 하위 50% 물량의 MIN MAX')
                        paths = [i for i in glob.glob('/appdata/abnormal_trend/pic/yh/P1F_CHH/*') if step_seq in i]
                        df = pl.DataFrame()
                        for path in paths:
                            if df.is_empty():
                                df = pl.read_csv(path)
                            else: df.extend( pl.read_csv(path) )
                        st.dataframe(df, height = 1000, width = 1000)
                    else:
                        st.markdown('err')
            with tab9:
                st.header('이상감지 메일 수신 설정')
                with st.form("email_form", clear_on_submit=False):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        email = st.text_input("이메일", placeholder="t1232.kang")
                    
                    col5, col6, col7, col8 = st.columns(4)
                    sdwt_options = list(line_rev.keys())
                    with col5:
                        sdwt = st.multiselect("sdwt", sdwt_options)

                    priority = st.segmented_control(
                        "priority",
                        options=["A", "B", "D", "M", "N"],
                        selection_mode="multi",   # 하나만 선택
                        default=["A", "B", "D", "M", "N"],
                    )
                    
                    col9, col10, col11, col12 = st.columns(4)
                    register = col9.form_submit_button("등록", use_container_width=True)
                    remove = col10.form_submit_button("제거", use_container_width=True)
                    
                if register:
                    if sdwt and email:
                        email = email.split('@')[0]
                        sdwt = str(sorted(sdwt))
                        priority = str(sorted(priority))
                        with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                            cursor = conn.cursor()
                            qry = f"""
                            INSERT INTO email (email, sdwt, priority)
                            VALUES ("{email}", "{sdwt}", "{priority}")
                            ON DUPLICATE KEY UPDATE
                                sdwt = VALUES(sdwt),
                                priority = VALUES(priority);
                            """ 
                            # print(qry)
                            cursor.execute(qry)
                            conn.commit()
                            cursor.close()
                        st.success("등록 완료")
                    else:
                        st.warning("이메일 혹은 분임조 선택 필요")
                if remove:
                    if email:
                        email = email.split('@')[0]
                        with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                            cursor = conn.cursor()
                            qry = f"""
                            DELETE FROM email
                            WHERE email = "{email}"
                            """ 
                            # print(qry)
                            cursor.execute(qry)
                            conn.commit()
                            cursor.close()
                        st.success("제거 완료")

                with pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, db=DB_NAME, charset='utf8', port=DB_PORT) as conn:
                    cursor = conn.cursor()
                    sql = f"""
                    SELECT DISTINCT email, sdwt, priority
                    FROM email
                    WHERE email = "{st.session_state.user}"
                    """.replace(',)',')')
                    cursor.execute(sql)
                    result = pd.DataFrame(cursor.fetchall(), columns=['email', 'sdwt', 'priority'])
                    cursor.close()  
                st.markdown(f"{st.session_state['claim_value'].get('username')}님 등록 리스트입니다")
                if result.empty:
                    st.markdown('등록 리스트가 없습니다')
                else:
                    st.dataframe(result, hide_index=True)
                    
        else:
            modal = Modal(key="secondary",title="USER INFO", max_width=450)
            with modal.container():
                st.write('타부서 또는 프로젝트라인 분들께서는 권한신청 부탁드립니다 (E기술팀 그게 나다)')


# ===== END: hard_spec_tail_full_question.py =====
