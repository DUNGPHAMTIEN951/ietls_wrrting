/**
 * theory_loader.js
 * Dynamically loads and renders IELTS theory data from master_data.json
 */

document.addEventListener('DOMContentLoaded', async () => {
    const pageTitle = document.title.toLowerCase();
    const h1Text = document.querySelector('h1')?.innerText.toLowerCase() || "";
    const fullText = pageTitle + " " + h1Text;

    // Determine keywords for filtering (now using arrays for better matching)
    let keywords = [];
    if (fullText.includes("increase") || fullText.includes("tăng")) keywords = ["increase", "tăng", "đi lên", "vượt", "đạt"];
    else if (fullText.includes("decrease") || fullText.includes("giảm")) keywords = ["decrease", "giảm", "đi xuống", "rơi", "tụt"];
    else if (fullText.includes("stable") || fullText.includes("ổn định")) keywords = ["stable", "ổn định", "không đổi", "duy trì"];
    else if (fullText.includes("fluctuate") || fullText.includes("biến động")) keywords = ["fluctuate", "biến động", "dao động"];
    else if (fullText.includes("task 2")) keywords = ["task 2", "nghị luận", "essay"];
    else keywords = [pageTitle.split('.')[0].trim().toLowerCase()]; // Fallback to first part of title

    try {
        console.log("Fetching data from master_data.json...");
        // Try multiple possible paths to accommodate different folder structures
        const paths = [
            '../../data/master_data.json',
            '../data/master_data.json',
            './data/master_data.json',
            'data/master_data.json'
        ];
        
        let response;
        for (const path of paths) {
            try {
                const res = await fetch(path);
                if (res.ok) {
                    response = res;
                    console.log(`Successfully loaded data from: ${path}`);
                    break;
                }
            } catch (e) {}
        }

        if (!response) throw new Error("Could not load master_data.json from any known path");
        const data = await response.json();

        console.log(`Filtering data for keywords: ${keywords.join(', ')}`);

        const matches = (text) => {
            if (!text) return false;
            const lowerText = text.toLowerCase();
            return keywords.some(k => lowerText.includes(k));
        };

        // Filter data
        const filteredVocab = data.vocabulary.filter(v =>
            matches(v.word) || matches(v.meaning_vi) || matches(v.source)
        ).slice(0, 15);

        const filteredStructures = data.structures.filter(s =>
            matches(s.formula) || matches(s.usage_vi) || matches(s.source)
        ).slice(0, 8);

        const filteredFlashcards = data.flashcards.filter(f =>
            matches(f.front) || matches(f.source)
        ).slice(0, 12);

        const filteredExercises = data.exercises.filter(e =>
            matches(e.text) || matches(e.source)
        ).slice(0, 5);

        console.log(`Found: ${filteredVocab.length} vocab, ${filteredStructures.length} structures, ${filteredFlashcards.length} flashcards, ${filteredExercises.length} exercises`);

        // Render sections
        renderVocabulary(filteredVocab);
        renderStructures(filteredStructures);
        renderFlashcards(filteredFlashcards);
        renderExercises(filteredExercises);

    } catch (error) {
        console.error("Error in theory_loader:", error);
    }
});

function renderVocabulary(vocab) {
    const tbody = document.querySelector('tbody');
    if (!tbody || vocab.length === 0) return;

    // Clear existing rows (optional, or append)
    // tbody.innerHTML = ""; 

    vocab.forEach(item => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td class="p-5">
                <div class="font-bold text-slate-900">${item.word}</div>
                <div class="text-[10px] text-blue-500 font-black uppercase mt-1">${item.type} | ${item.pron}</div>
            </td>
            <td class="p-5 font-medium text-slate-600">${item.meaning_vi}</td>
            <td class="p-5 italic text-slate-500">"${item.example}"</td>
        `;
        tbody.appendChild(row);
    });
}

function renderStructures(structures) {
    const container = document.querySelector('.grid.grid-cols-1.md:grid-cols-2.gap-8');
    if (!container || structures.length === 0) return;

    structures.forEach(item => {
        const card = document.createElement('div');
        card.className = "p-8 bg-white border border-slate-100 rounded-3xl hover-card shadow-sm";
        card.innerHTML = `
            <div class="text-[10px] font-black text-indigo-400 uppercase tracking-[0.2em] mb-4">${item.usage_vi}</div>
            <p class="text-lg font-bold text-slate-800 leading-snug">"${item.example_band8}"</p>
            <div class="mt-6 flex flex-wrap gap-2">
                <span class="px-3 py-1 bg-indigo-50 text-indigo-600 text-[10px] font-black rounded-lg">${item.formula}</span>
            </div>
        `;
        container.appendChild(card);
    });
}

function renderFlashcards(cards) {
    const grid = document.getElementById('flashcard-grid');
    if (!grid || cards.length === 0) return;

    cards.forEach(item => {
        const card = document.createElement('div');
        card.className = "flashcard w-full max-w-[280px] h-64 perspective-1000 group cursor-pointer";
        card.onclick = () => card.classList.toggle('flipped');
        card.innerHTML = `
            <div class="flashcard-inner relative w-full h-full text-center">
                <div class="flashcard-front bg-slate-50 border-2 border-dashed border-slate-200 rounded-[2.5rem] p-8 flex flex-col items-center justify-center">
                    <span class="text-[10px] font-black text-blue-400 uppercase tracking-widest mb-4">Review Card</span>
                    <h3 class="text-xl font-black text-slate-800 italic">${item.front}</h3>
                    <p class="text-slate-400 text-[10px] mt-6 flex items-center gap-2 italic">Chạm để lật...</p>
                </div>
                <div class="flashcard-back bg-blue-600 rounded-[2.5rem] p-8 flex flex-col items-center justify-center text-white shadow-xl shadow-blue-500/20">
                    <span class="text-[10px] font-black text-blue-200 uppercase tracking-widest mb-4">Answer</span>
                    <h3 class="text-lg font-black mb-2 tracking-tight">${item.back}</h3>
                </div>
            </div>
        `;
        grid.appendChild(card);
    });
}

function renderExercises(exercises) {
    // Check if there is a section for exercises
    let section = document.getElementById('exercise-section');
    if (!section) {
        // Create it if it doesn't exist
        const lastSection = document.querySelector('section:last-of-type');
        section = document.createElement('section');
        section.id = "exercise-section";
        section.className = "mb-24";
        section.innerHTML = `
            <div class="flex items-center gap-3 mb-8">
                 <span class="w-8 h-8 rounded-lg bg-orange-100 flex items-center justify-center text-orange-600 font-black text-xs">AI</span>
                 <h2 class="text-xl font-black text-slate-900 uppercase tracking-tighter">Bài tập thực hành (Generated)</h2>
            </div>
            <div class="space-y-6" id="exercise-list"></div>
        `;
        lastSection.parentNode.insertBefore(section, lastSection);
    }

    const list = document.getElementById('exercise-list');
    exercises.forEach((item, index) => {
        const ex = document.createElement('div');
        ex.className = "p-6 bg-slate-50 rounded-2xl border border-slate-100";
        let optionsHtml = "";
        if (item.options) {
            Object.entries(item.options).forEach(([key, val]) => {
                optionsHtml += `<div class="text-sm mt-2"><strong>${key}:</strong> ${val}</div>`;
            });
        }
        ex.innerHTML = `
            <div class="font-bold text-slate-800">${index + 1}. ${item.text}</div>
            <div class="mt-2">${optionsHtml}</div>
            <details class="mt-4">
                <summary class="text-xs font-black text-blue-600 cursor-pointer uppercase">Xem đáp án</summary>
                <div class="mt-2 p-4 bg-white rounded-xl text-sm border border-blue-50">
                    <div class="font-bold text-emerald-600">Đáp án: ${item.answer}</div>
                    <div class="mt-1 text-slate-500">${item.explanation_vi}</div>
                </div>
            </details>
        `;
        list.appendChild(ex);
    });
}
