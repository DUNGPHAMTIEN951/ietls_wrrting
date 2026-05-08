import os
import re
import mysql.connector
import json
import asyncio
from gemini_webapi import GeminiClient

# Config
LESSONS_DIR = r"d:\ietls_wrrting\pages\lessons"
ASSETS_DIR = r"../../assets/task2_diagrams"
FILES = [
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
    "WRITING_28_IDEAS_for_TASK_2_part43.html"
]

DIAGRAM_ASSETS = [
    "unit1_basic_needs_diagram.jpg", "unit1_global_role_diagram.jpg", "unit1_higher_needs_diagram.jpg",
    "unit2_biodiversity_diagram.jpg", "unit2_energy_diagram.jpg", "unit2_solutions_diagram.jpg", "unit2_throw_away_society_diagram.jpg",
    "unit3_effects_diagram.jpg", "unit3_legal_aspects_diagram.jpg", "unit3_structure_causes_diagram.jpg",
    "unit4_gender___leadership_diagram.jpg", "unit4_old_vs_young_diagram.jpg", "unit4_security_vs_satisfaction_diagram.jpg", "unit4_work_life_balance_diagram.jpg",
    "unit5_breadth_vs_depth_diagram.jpg", "unit5_curriculum_diagram.jpg", "unit5_learning_effectiveness_diagram.jpg", "unit5_national_vs_global_diagram.jpg", "unit5_scholarships_diagram.jpg", "unit5_universal_access_diagram.jpg",
    "unit7_ai___robots_diagram.jpg", "unit7_driverless_cars_diagram.jpg", "unit7_research_control_diagram.jpg", "unit7_space_tech_diagram.jpg",
    "unit8_causes_diagram.jpg", "unit8_common_practices_diagram.jpg", "unit8_cybercrime_diagram.jpg", "unit8_other_measures_diagram.jpg",
    "unit9_benefits_diagram.jpg", "unit9_gap_year_drawbacks_diagram.jpg", "unit9_tourism_drawbacks_diagram.jpg",
    "unit10_cosmetic_surgery_diagram.jpg", "unit10_sedentary_lifestyle_diagram.jpg", "unit10_sports_exercise_diagram.jpg", "unit10_sugary_fast_food_diagram.jpg",
    "unit11_advertising_diagram.jpg", "unit11_imports_diagram.jpg", "unit11_shopping_diagram.jpg",
    "unit12_globalization_diagram.jpg", "unit12_language_diagram.jpg", "unit12_museums_diagram.jpg", "unit12_traditions_diagram.jpg",
    "unit13_animal_testing_diagram.jpg"
]

async def main():
    # Setup Gemini
    with open(r"d:\ietls_wrrting\cookie_pro.js", 'r') as f:
        cookies = json.load(f)
    client = GeminiClient(cookies=cookies)
    await client.init()
    chat = client.start_chat()

    for fname in FILES:
        path = os.path.join(LESSONS_DIR, fname)
        if not os.path.exists(path): continue
        
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        
        # 1. Ask Gemini to match
        text_preview = re.sub(r'<[^>]+>', ' ', html)[:2000]
        prompt = f"""Analyze this IELTS lesson content and pick the MOST RELEVANT diagram from the list below.
CONTENT: {text_preview}

LIST OF DIAGRAMS:
{", ".join(DIAGRAM_ASSETS)}

Return ONLY the filename of the best match. If none fit perfectly, pick the closest one."""

        try:
            print(f"Matching diagram for {fname}...")
            response = await chat.send_message(prompt)
            match = response.text.strip()
            # Clean up response
            best_img = None
            for img in DIAGRAM_ASSETS:
                if img in match:
                    best_img = img
                    break
            
            if best_img:
                print(f"  -> Best Match: {best_img}")
                # 2. Replace Mermaid or add after H1
                img_tag = f'''
                <div class="my-10 p-4 glass-card rounded-3xl shadow-2xl transition-all duration-500 hover:scale-[1.01] overflow-hidden">
                    <div class="text-xs font-semibold text-indigo-500 mb-2 uppercase tracking-widest text-center">Conceptual Visualization</div>
                    <img src="{ASSETS_DIR}/{best_img}" alt="Concept Diagram" class="w-full h-auto rounded-2xl">
                </div>
                '''
                
                # Replace existing mermaid blocks if any
                if '<pre class="mermaid">' in html:
                    new_html = re.sub(r'<pre class="mermaid">.*?</pre>', img_tag, html, flags=re.DOTALL)
                elif '<div class="mermaid">' in html:
                    new_html = re.sub(r'<div class="mermaid">.*?</div>', img_tag, html, flags=re.DOTALL)
                else:
                    # Inject after H1 if no mermaid found
                    new_html = html.replace('</h1>', '</h1>' + img_tag, 1)
                
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(new_html)
                print(f"  [OK] Updated {fname}")
            else:
                print(f"  [SKIP] Could not find a clear match for {fname}")
        except Exception as e:
            print(f"  [ERROR] {e}")

if __name__ == "__main__":
    asyncio.run(main())
