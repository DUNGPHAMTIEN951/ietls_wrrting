"""
Bulk enqueue lesson HTML files for AI practice generation.
The Pro worker will read each file, generate 100+ diverse exercises,
and inject them back into the HTML file automatically.
"""
import mysql.connector
import json
import hashlib
import os

LESSONS_DIR = r"d:\ietls_wrrting\pages\lessons"

FILES = [
    "WRITING_1A__LY_THUYET_TU_VUNG_VA_CAU_TRUC_TASK_1_-_HOC_THUAT_-_ANH_VIET_part3.html",
    "WRITING_1A__LY_THUYET_TU_VUNG_VA_CAU_TRUC_TASK_1_-_HOC_THUAT_-_ANH_VIET_part5.html",
    "WRITING_1A__LY_THUYET_TU_VUNG_VA_CAU_TRUC_TASK_1_-_HOC_THUAT_-_ANH_VIET_part7.html",
    "WRITING_1A_LY_THUYE_T_TU_VU_NG_VA_CA_U_TRU_C_TASK_1_HO_C_THUA_T_ANH_VIE_T_part2.html",
    "WRITING_1A_LY_THUYE_T_TU_VU_NG_VA_CA_U_TRU_C_TASK_1_HO_C_THUA_T_ANH_VIE_T_part7.html",
    "WRITING_1A_LY_THUYE_T_TU_VU_NG_VA_CA_U_TRU_C_TASK_1_HO_C_THUA_T_ANH_VIE_T_part9.html",
    "WRITING_1A_LY_THUYE_T_TU_VU_NG_VA_CA_U_TRU_C_TASK_1_HO_C_THUA_T_ANH_VIE_T_part10.html",
    "WRITING_1B_LY_THUYE_T_TU_VU_NG_VA_CA_U_TRU_C_TASK_1_HO_C_THUA_T_TIE_NG_VIE_T_part9.html",
    "WRITING_3A_ĐA_P_A_N_BA_I_TA_P_TASK_1_HO_C_THUA_T_TIE_NG_ANH_part4.html",
    "WRITING_3A_ĐA_P_A_N_BA_I_TA_P_TASK_1_HO_C_THUA_T_TIE_NG_ANH_part9.html",
    "WRITING_3B_ĐA_P_A_N_BA_I_TA_P_TASK_1_HO_C_THUA_T_TIE_NG_VIE_T_part7.html",
    "WRITING_4A_BA_I_VA_N_MA_U_TASK_2_ANH_VIE_T_part2.html",
    "WRITING_4A_BA_I_VA_N_MA_U_TASK_2_ANH_VIE_T_part7.html",
    "WRITING_4B_BA_I_VA_N_MA_U_TASK_2_TIE_NG_VIE_T_part7.html",
    "WRITING_5A_DA_N_Y_VA_CU_M_TU_TRONG_BA_I_VIE_T_TASK_2_ANH_VIE_T_VERS2023_part1.html",
    "WRITING_5A_DA_N_Y_VA_CU_M_TU_TRONG_BA_I_VIE_T_TASK_2_ANH_VIE_T_VERS2023_part8.html",
    "WRITING_5A_DA_N_Y_VA_CU_M_TU_TRONG_BA_I_VIE_T_TASK_2_ANH_VIE_T_VERS2023_part20.html",
    "WRITING_5B_DA_N_Y_VA_CU_M_TU_TRONG_BA_I_VIE_T_TASK_2_TIE_NG_VIE_T_VER2023_part8.html",
    "WRITING_5B_DA_N_Y_VA_CU_M_TU_TRONG_BA_I_VIE_T_TASK_2_TIE_NG_VIE_T_VER2023_part9.html",
    "WRITING_7_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2017_part11.html",
    "WRITING_7_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2017_part14.html",
    "WRITING_8_BA_I_TA_P_MA_U_TASK_1_2_ZIM2018_part7.html",
    "WRITING_8_BA_I_TA_P_MA_U_TASK_1_2_ZIM2018_part9.html",
    "WRITING_8_BA_I_TA_P_MA_U_TASK_1_2_ZIM2018_part13.html",
    "WRITING_8_BA_I_TA_P_MA_U_TASK_1_2_ZIM2018_part16.html",
    "WRITING_9_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2019_part8.html",
    "WRITING_9_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2019_part18.html",
    "WRITING_9_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2019_part23.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part1.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part2.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part3.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part4.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part5.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part6.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part7.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part8.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part9.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part10.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part13.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part14.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part15.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part16.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part17.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part18.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part19.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part20.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part21.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part22.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part23.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part24.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part25.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part26.html",
    "WRITING_11A_BA_I_TA_P_TASK_1_TO_NG_QUA_T_TIE_NG_ANH_part27.html",
    "WRITING_11A_BAI_TAP_TASK_1__TONG_QUAT__TIENG_ANH_part9.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part1.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part2.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part3.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part4.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part5.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part6.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part7.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part8.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part9.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part10.html",
    "WRITING_15B_LUYE_N_VIE_T_CA_U_TASK_1_HO_C_THUA_T_part11.html",
    "WRITING_15B_LUYEN_VIET_CAU_TASK_1_HOC_THUAT_part1.html",
    "WRITING_15B_LUYEN_VIET_CAU_TASK_1_HOC_THUAT_part2.html",
    "WRITING_15B_LUYEN_VIET_CAU_TASK_1_HOC_THUAT_part3.html",
    "WRITING_15B_LUYEN_VIET_CAU_TASK_1_HOC_THUAT_part4.html",
    "WRITING_15B_LUYEN_VIET_CAU_TASK_1_HOC_THUAT_part5.html",
    "WRITING_15B_LUYEN_VIET_CAU_TASK_1_HOC_THUAT_part6.html",
    "WRITING_15B_LUYEN_VIET_CAU_TASK_1_HOC_THUAT_part7.html",
    "WRITING_15B_LUYEN_VIET_CAU_TASK_1_HOC_THUAT_part8.html",
    "WRITING_15B_LUYEN_VIET_CAU_TASK_1_HOC_THUAT_part9.html",
    "WRITING_15B_LUYEN_VIET_CAU_TASK_1_HOC_THUAT_part10.html",
    "WRITING_16B__LUYEN_VIET_CAU_TASK_2_HOC_THUAT_part1.html",
    "WRITING_16B__LUYEN_VIET_CAU_TASK_2_HOC_THUAT_part2.html",
    "WRITING_16B__LUYEN_VIET_CAU_TASK_2_HOC_THUAT_part3.html",
    "WRITING_16B__LUYEN_VIET_CAU_TASK_2_HOC_THUAT_part4.html",
    "WRITING_16B__LUYEN_VIET_CAU_TASK_2_HOC_THUAT_part5.html",
    "WRITING_16B__LUYEN_VIET_CAU_TASK_2_HOC_THUAT_part6.html",
    "WRITING_16B__LUYEN_VIET_CAU_TASK_2_HOC_THUAT_part7.html",
    "WRITING_16B__LUYEN_VIET_CAU_TASK_2_HOC_THUAT_part8.html",
    "WRITING_16B__LUYEN_VIET_CAU_TASK_2_HOC_THUAT_part9.html",
    "WRITING_16B__LUYEN_VIET_CAU_TASK_2_HOC_THUAT_part10.html",
    "WRITING_16B_LUYE_N_VIE_T_CA_U_TASK_2_HO_C_THUA_T_part1.html",
    "WRITING_16B_LUYE_N_VIE_T_CA_U_TASK_2_HO_C_THUA_T_part2.html",
    "WRITING_16B_LUYE_N_VIE_T_CA_U_TASK_2_HO_C_THUA_T_part3.html",
    "WRITING_16B_LUYE_N_VIE_T_CA_U_TASK_2_HO_C_THUA_T_part4.html",
    "WRITING_16B_LUYE_N_VIE_T_CA_U_TASK_2_HO_C_THUA_T_part5.html",
    "WRITING_16B_LUYE_N_VIE_T_CA_U_TASK_2_HO_C_THUA_T_part6.html",
    "WRITING_16B_LUYE_N_VIE_T_CA_U_TASK_2_HO_C_THUA_T_part7.html",
    "WRITING_16B_LUYE_N_VIE_T_CA_U_TASK_2_HO_C_THUA_T_part8.html",
    "WRITING_16B_LUYE_N_VIE_T_CA_U_TASK_2_HO_C_THUA_T_part9.html",
    "WRITING_16B_LUYE_N_VIE_T_CA_U_TASK_2_HO_C_THUA_T_part10.html",
    "WRITING_18A__LUYEN_VIET_CAU_NGU_PHAP_-_TIENG_ANH_part1.html",
    "WRITING_18A__LUYEN_VIET_CAU_NGU_PHAP_-_TIENG_ANH_part2.html",
    "WRITING_18A__LUYEN_VIET_CAU_NGU_PHAP_-_TIENG_ANH_part3.html",
    "WRITING_18A__LUYEN_VIET_CAU_NGU_PHAP_-_TIENG_ANH_part4.html",
    "WRITING_18A__LUYEN_VIET_CAU_NGU_PHAP_-_TIENG_ANH_part5.html",
    "WRITING_18A__LUYEN_VIET_CAU_NGU_PHAP_-_TIENG_ANH_part6.html",
    "WRITING_18A__LUYEN_VIET_CAU_NGU_PHAP_-_TIENG_ANH_part7.html",
    "WRITING_18A__LUYEN_VIET_CAU_NGU_PHAP_-_TIENG_ANH_part8.html",
    "WRITING_18A__LUYEN_VIET_CAU_NGU_PHAP_-_TIENG_ANH_part9.html",
    "WRITING_18A__LUYEN_VIET_CAU_NGU_PHAP_-_TIENG_ANH_part10.html",
    "WRITING_18A_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_ANH_part1.html",
    "WRITING_18A_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_ANH_part2.html",
    "WRITING_18A_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_ANH_part3.html",
    "WRITING_18A_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_ANH_part4.html",
    "WRITING_18A_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_ANH_part5.html",
    "WRITING_18A_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_ANH_part6.html",
    "WRITING_18A_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_ANH_part7.html",
    "WRITING_18A_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_ANH_part8.html",
    "WRITING_18A_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_ANH_part9.html",
    "WRITING_18A_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_ANH_part10.html",
    "WRITING_18B_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_VIE_T_part1.html",
    "WRITING_18B_LUYE_N_VIE_T_CA_U_NGU_PHA_P_TIE_NG_VIE_T_part10.html",
    "WRITING_19_-_BAI_TAP_MAU_TASK_1__2_ZIM_2020_part2.html",
    "WRITING_19_-_BAI_TAP_MAU_TASK_1__2_ZIM_2020_part4.html",
    "WRITING_19_-_BAI_TAP_MAU_TASK_1__2_ZIM_2020_part8.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part12.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part13.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part19.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part20.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part21.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part22.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part23.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part24.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part25.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part26.html",
    "WRITING_19_BA_I_TA_P_MA_U_TASK_1_2_ZIM_2020_part28.html",
    "WRITING_21_THỰC_HÀNH_MẪU_CÂU_BÀI_TẬP_part2.html",
    "WRITING_21_THỰC_HÀNH_MẪU_CÂU_BÀI_TẬP_part4.html",
    "WRITING_21_THỰC_HÀNH_MẪU_CÂU_BÀI_TẬP_part9.html",
    "WRITING_21_THỰC_HÀNH_MẪU_CÂU_BÀI_TẬP_part10.html",
    "WRITING_21_THỰC_HÀNH_MẪU_CÂU_ĐÁP_ÁN_part5.html",
    "WRITING_22_100_WRITING_MISTAKES_part7.html",
    "WRITING_22_100_WRITING_MISTAKES_part9.html",
    "WRITING_23_WRITING_TASK_2_TEMPLATES_part1.html",
    "WRITING_23_WRITING_TASK_2_TEMPLATES_part2.html",
    "WRITING_23_WRITING_TASK_2_TEMPLATES_part6.html",
    "WRITING_24_TỔNG_HỢP_CÁC_ĐỀ_PROCESS_part5.html",
    "WRITING_24_TỔNG_HỢP_CÁC_ĐỀ_PROCESS_part6.html",
    "WRITING_24_TỔNG_HỢP_CÁC_ĐỀ_PROCESS_part9.html",
    "WRITING_25_CA_P_NHA_T_ĐE_THI_MO_I_NHA_T_part10.html",
    "WRITING_26_IELTS_ESSAY_ANALYSIS_part6.html",
    "WRITING_28_IDEAS_for_TASK_2_part3.html",
    "WRITING_28_IDEAS_for_TASK_2_part5.html",
    "WRITING_28_IDEAS_for_TASK_2_part7.html",
    "WRITING_28_IDEAS_for_TASK_2_part12.html",
    "WRITING_28_IDEAS_for_TASK_2_part13.html",
    "WRITING_28_IDEAS_for_TASK_2_part17.html",
    "WRITING_28_IDEAS_for_TASK_2_part22.html",
    "WRITING_28_IDEAS_for_TASK_2_part24.html",
    "WRITING_28_IDEAS_for_TASK_2_part26.html",
    "WRITING_28_IDEAS_for_TASK_2_part30.html",
    "WRITING_28_IDEAS_for_TASK_2_part39.html",
    "WRITING_28_IDEAS_for_TASK_2_part43.html",
    "WRITING_29_ACADEMY_PHRASES_TASK_1_part1.html",
    "WRITING_30_REVIEW_TEST_2022_part11.html",
    "WRITING_31_REVIEW_TEST_2023_part6.html",
    "WRITING_31_REVIEW_TEST_2023_part23.html",
    "WRITING_31_REVIEW_TEST_2023_part33.html",
    "WRITING_31_REVIEW_TEST_2023_part42.html",
    "WRITING_31_REVIEW_TEST_2023_part44.html",
    "WRITING_31_REVIEW_TEST_2023_part59.html",
    "WRITING_31_REVIEW_TEST_2023_part71.html",
    "WRITING_31_REVIEW_TEST_2023_part72.html",
    "WRITING_31_REVIEW_TEST_2023_part85.html",
    "WRITING_31_REVIEW_TEST_2023_part89.html",
]

import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    conn = mysql.connector.connect(host='localhost', user='root', password='', database='ielts_speaking')
    cur = conn.cursor()
    
    enqueued = 0
    missing = 0
    
    for fname in FILES:
        full_path = os.path.join(LESSONS_DIR, fname)
        if not os.path.exists(full_path):
            print(f"[MISSING] {fname}")
            missing += 1
            continue
        
        task_data = json.dumps({
            "filename": fname,
            "file_path": full_path
        }, ensure_ascii=False)
        
        hash_str = f"practice_{fname}"
        task_hash = hashlib.sha256(hash_str.encode()).hexdigest()
        
        sql = """
            INSERT INTO ai_tasks (task_hash, task_type, task_data, status)
            VALUES (%s, %s, %s, 'pending')
            ON DUPLICATE KEY UPDATE
                status = IF(status IN ('failed'), 'pending', status)
        """
        cur.execute(sql, (task_hash, "practice_generation", task_data))
        enqueued += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"\n{'='*50}")
    print(f"DONE: Enqueued {enqueued} practice tasks into PRO queue.")
    print(f"WARNING: Missing files: {missing}")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()

