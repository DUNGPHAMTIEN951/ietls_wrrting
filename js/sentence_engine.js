/**
 * IELTS Writing Practice Engine
 * Handles dynamic loading and rendering of sentence banks and practice materials.
 */

const IELTSPracticeHub = {
    data: {
        grammar: [],
        task1: [],
        task2: [],
        writing21: [],
        review2020: [],
        task2Templates: [],
        writingMistakes: [],
        task1Process: [],
        review2022: [],
        task1Words: [],
        task2Ideas: [],
        simonGuide: [],
        review2023: []
    },

    async loadData(type) {
        const fileMap = {
            'grammar': '/data/grammar_sentences.json',
            'task1': '/data/academic_task1_sentences.json',
            'task2': '/data/academic_task2_sentences.json',
            'writing21': '/data/writing_21_sentences.json',
            'review2020': '/data/writing_2020_review.json',
            'task2Templates': '/data/task2_templates.json',
            'writingMistakes': '/data/writing_mistakes.json',
            'task1Process': '/data/task1_process.json',
            'review2022': '/data/writing_2022_review.json',
            'task1Words': '/data/writing_task1_academic_words.json',
            'task2Ideas': '/data/writing_task2_ideas.json',
            'simonGuide': '/data/simon_essay_guide.json',
            'review2023': '/data/writing_2023_review.json'
        };

        if (!fileMap[type]) return;

        try {
            const response = await fetch(fileMap[type]);
            this.data[type] = await response.json();
            console.log(`Loaded ${this.data[type].length} items for ${type}`);
            return this.data[type];
        } catch (error) {
            console.error(`Error loading ${type} data:`, error);
        }
    },

    renderGrammar(containerId, filterCategory = 'ALL') {
        const container = document.getElementById(containerId);
        if (!container) return;

        let items = this.data.grammar;
        if (filterCategory !== 'ALL') {
            items = items.filter(item => item.category === filterCategory);
        }

        container.innerHTML = items.map((item, index) => `
            <div class="p-4 border-b border-gray-100 hover:bg-gray-50 transition-colors group" id="grammar-${item.id}">
                <div class="flex items-start justify-between">
                    <div class="flex-1">
                        <span class="inline-block px-2 py-1 text-xs font-semibold text-blue-600 bg-blue-50 rounded mb-2 uppercase italic">${item.category} #${item.id}</span>
                        <p class="text-gray-800 font-medium mb-2">${item.vn}</p>
                        <div id="ans-grammar-${item.id}" class="hidden mt-2 p-3 bg-green-50 border-l-4 border-green-400 text-green-800 font-inter italic">
                            ${item.en}
                        </div>
                    </div>
                    <button onclick="IELTSPracticeHub.toggleAnswer('grammar-${item.id}')" 
                            class="ml-4 px-3 py-1 text-sm bg-gray-200 text-gray-700 rounded-full hover:bg-blue-600 hover:text-white transition-all">
                        Reveal
                    </button>
                </div>
            </div>
        `).join('');
    },

    renderAcademic(containerId, type = 'task1', filterCode = 'ALL') {
        const container = document.getElementById(containerId);
        if (!container) return;

        let items = (type === 'task1') ? this.data.task1 : this.data.task2;
        if (filterCode !== 'ALL') {
            items = items.filter(item => item.code === filterCode);
        }

        container.innerHTML = items.map((item, index) => `
            <div class="p-4 border-b border-gray-100 hover:bg-gray-100 transition-colors" id="${type}-${item.code}-${item.id}">
                <div class="flex items-start justify-between">
                    <div class="flex-1">
                        <span class="text-xs text-gray-500 font-mono">[${item.code}]</span>
                        <p class="text-gray-800 mb-2">${item.vn}</p>
                        <div id="ans-${type}-${item.code}-${item.id}" class="hidden mt-2 p-3 bg-indigo-50 text-indigo-900 rounded font-medium italic border-l-4 border-indigo-400">
                            ${item.en}
                        </div>
                    </div>
                    <button onclick="IELTSPracticeHub.toggleAnswer('${type}-${item.code}-${item.id}')" 
                            class="ml-4 text-xs bg-indigo-100 text-indigo-600 px-2 py-1 rounded hover:bg-indigo-600 hover:text-white transition-all uppercase font-bold">
                        Check
                    </button>
                </div>
            </div>
        `).join('');
    },

    renderWriting21(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const items = this.data.writing21;
        container.innerHTML = items.map((item, index) => `
             <div class="p-4 border-b border-gray-100 bg-white rounded-lg mb-2 shadow-sm border-l-4 border-amber-400" id="w21-${item.code}-${item.id}">
                <div class="flex items-start justify-between">
                    <div class="flex-1">
                        <span class="text-xs text-amber-600 font-bold bg-amber-50 px-2 py-0.5 rounded italic">Template ${item.code}</span>
                        <p class="text-gray-800 mt-1">${item.vn}</p>
                        <div id="ans-w21-${item.code}-${item.id}" class="hidden mt-3 p-3 bg-slate-800 text-white rounded font-inter italic leading-relaxed">
                            ${item.en}
                        </div>
                    </div>
                    <button onclick="IELTSPracticeHub.toggleAnswer('w21-${item.code}-${item.id}')" 
                            class="ml-4 px-3 py-1 text-xs border border-amber-400 text-amber-600 rounded hover:bg-amber-400 hover:text-white transition-all">
                        Reveal
                    </button>
                </div>
            </div>
        `).join('');
    },

    toggleAnswer(fullId) {
        const ansDiv = document.getElementById(`ans-${fullId}`);
        if (ansDiv) {
            ansDiv.classList.toggle('hidden');
            const btn = ansDiv.parentElement.querySelector('button');
            if (btn) {
                btn.textContent = ansDiv.classList.contains('hidden') ? 'Reveal' : 'Hide';
                if (!ansDiv.classList.contains('hidden')) {
                    btn.classList.replace('bg-gray-200', 'bg-blue-600');
                    btn.classList.add('text-white');
                } else {
                    btn.classList.replace('bg-blue-600', 'bg-gray-200');
                    btn.classList.remove('text-white');
                }
            }
        }
    },

    renderTask1Process(containerId, filter = 'ALL') {
        const container = document.getElementById(containerId);
        if (!container) return;

        const data = this.data.task1Process;
        if (!data || !data.samples) return;

        let samples = data.samples;
        if (filter !== 'ALL') {
            samples = samples.filter(s => s.type === filter);
        }

        const theory = data.theory;

        container.innerHTML = `
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <!-- Sidebar: Theory & Sequencing -->
                <div class="lg:col-span-1 space-y-6">
                    <div class="bg-indigo-900 text-white p-6 rounded-2xl shadow-lg">
                        <h3 class="text-xl font-bold mb-4 flex items-center">
                            <i data-lucide="book-open" class="mr-2 w-5 h-5"></i> Lý thuyết Process
                        </h3>
                        <p class="text-indigo-200 text-sm leading-relaxed mb-6">${theory.definition}</p>
                        
                        <div class="space-y-4">
                            ${theory.types.map(t => `
                                <div class="bg-indigo-800/50 p-4 rounded-xl border border-indigo-700">
                                    <h4 class="font-bold text-white mb-1">${t.name}</h4>
                                    <p class="text-xs text-indigo-300 mb-2">${t.description}</p>
                                    <div class="flex flex-wrap gap-1">
                                        ${t.examples.map(ex => `<span class="text-[10px] bg-indigo-700 px-2 py-0.5 rounded text-indigo-100">${ex}</span>`).join('')}
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>

                    <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm">
                        <h3 class="text-lg font-bold text-slate-800 mb-4 flex items-center">
                            <i data-lucide="list-ordered" class="mr-2 w-5 h-5 text-indigo-500"></i> Các bước làm bài
                        </h3>
                        <ul class="space-y-3">
                            ${theory.steps.map(step => `
                                <li class="flex items-start gap-3 text-sm text-slate-600">
                                    <div class="mt-1 flex-shrink-0 w-2 h-2 bg-indigo-400 rounded-full"></div>
                                    ${step}
                                </li>
                            `).join('')}
                        </ul>
                    </div>

                    <div class="bg-emerald-50 p-6 rounded-2xl border border-emerald-100 shadow-sm">
                        <h3 class="text-lg font-bold text-emerald-900 mb-4 flex items-center">
                            <i data-lucide="languages" class="mr-2 w-5 h-5 text-emerald-600"></i> Sequencing Language
                        </h3>
                        <div class="space-y-4">
                            <div>
                                <p class="text-xs font-bold text-emerald-700 uppercase mb-2">Trình tự (Sequential):</p>
                                <div class="flex flex-wrap gap-2">
                                    ${theory.sequencing_language.sequential.map(word => `<span class="bg-white px-2 py-1 rounded text-xs text-emerald-800 border border-emerald-200">${word}</span>`).join('')}
                                </div>
                            </div>
                            <div>
                                <p class="text-xs font-bold text-emerald-700 uppercase mb-2">Đồng thời (Simultaneous):</p>
                                <div class="flex flex-wrap gap-2">
                                    ${theory.sequencing_language.simultaneous.map(word => `<span class="bg-white px-2 py-1 rounded text-xs text-emerald-800 border border-emerald-200">${word}</span>`).join('')}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Main: Samples -->
                <div class="lg:col-span-2 space-y-8">
                    <div class="flex items-center justify-between mb-2">
                        <h3 class="text-2xl font-bold text-slate-800">Thư viện Bài mẫu Process</h3>
                        <div class="text-slate-400 text-sm font-medium">${samples.length} bài mẫu</div>
                    </div>

                    ${samples.map((sample, idx) => `
                        <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden animate-fadeIn" style="animation-delay: ${idx * 0.1}s">
                            <div class="p-6">
                                <div class="flex justify-between items-start mb-4">
                                    <div>
                                        <div class="flex items-center gap-2 mb-1">
                                            <span class="px-2 py-0.5 bg-slate-100 text-slate-500 rounded text-[10px] font-bold uppercase tracking-wider">${sample.type}</span>
                                            <span class="text-slate-400 text-xs">• 40-60 mins</span>
                                        </div>
                                        <h4 class="text-xl font-bold text-slate-800">${sample.title}</h4>
                                    </div>
                                    <button onclick="this.nextElementSibling.classList.toggle('hidden')" class="p-2 hover:bg-slate-100 rounded-lg transition-colors">
                                        <i data-lucide="chevron-down" class="w-5 h-5 text-slate-400"></i>
                                    </button>
                                </div>

                                <div class="space-y-4">
                                    <div class="p-4 bg-slate-50 rounded-xl border border-slate-100">
                                        <p class="text-xs font-bold text-indigo-600 uppercase mb-2">Mở bài (Introduction):</p>
                                        <p class="text-slate-700 italic font-serif">${sample.introduction}</p>
                                    </div>
                                    <div class="p-4 bg-indigo-50/30 rounded-xl border border-indigo-100/50">
                                        <p class="text-xs font-bold text-indigo-700 uppercase mb-2">Tổng quan (Overview):</p>
                                        <p class="text-slate-800 font-medium">${sample.overview}</p>
                                    </div>
                                    
                                    <div class="space-y-3">
                                        <p class="text-xs font-bold text-slate-400 uppercase">Thân bài (Body Paragraphs):</p>
                                        ${sample.details.map(p => `<p class="text-slate-700 leading-relaxed text-sm bg-white p-3 rounded-lg border border-slate-100 shadow-sm font-serif">${p}</p>`).join('')}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
        lucide.createIcons();
    },

    renderWritingMistakes(containerId, category = 'ALL') {
        const container = document.getElementById(containerId);
        if (!container) return;

        let items = this.data.writingMistakes;
        if (category !== 'ALL') {
            items = items.filter(item => item.category === category);
        }

        container.innerHTML = `
            <div class="space-y-4">
                ${items.map((item, index) => `
                    <div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden hover:border-indigo-300 transition-all duration-300">
                        <div class="p-4 flex items-start gap-4">
                            <div class="flex-shrink-0 w-10 h-10 bg-indigo-50 rounded-full flex items-center justify-center text-indigo-600 font-bold">
                                ${index + 1}
                            </div>
                            <div class="flex-grow">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="text-[10px] font-bold uppercase py-0.5 px-2 bg-slate-100 text-slate-500 rounded">${item.category}</span>
                                    <h4 class="font-bold text-slate-800">${item.title}</h4>
                                </div>
                                <div class="mt-3 p-3 bg-red-50 border-l-4 border-red-400 rounded-r-lg">
                                    <p class="text-xs font-bold text-red-700 uppercase mb-1">Sai (Incorrect):</p>
                                    <p class="text-slate-700 font-serif line-through decoration-red-500/50">${item.wrong}</p>
                                </div>
                                <div class="mt-2 p-3 bg-emerald-50 border-l-4 border-emerald-400 rounded-r-lg">
                                    <p class="text-xs font-bold text-emerald-700 uppercase mb-1">Đúng (Correct):</p>
                                    <p class="text-slate-800 font-serif font-medium">${item.right}</p>
                                </div>
                                ${item.explanation ? `
                                    <div class="mt-3 text-sm text-slate-600 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-100 italic">
                                        <strong>Giải thích:</strong> ${item.explanation}
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                `).join('')}
                ${items.length === 0 ? '<div class="text-center py-10 text-slate-400 italic">Chưa có dữ liệu cho mục này.</div>' : ''}
            </div>
        `;
    },

    renderTask2Templates(containerId, templateId = 'ALL') {
        const container = document.getElementById(containerId);
        if (!container) return;

        let items = this.data.task2Templates;
        if (templateId !== 'ALL') {
            items = items.filter(item => item.id === templateId || item.type === templateId);
        }

        container.innerHTML = items.map(tpl => `
            <div class="mb-10 bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden animate-fadeIn">
                <div class="bg-indigo-600 p-5 text-white">
                    <h3 class="text-xl font-bold">${tpl.title}</h3>
                    <p class="text-indigo-100 text-sm mt-1">${tpl.description}</p>
                </div>
                
                <div class="p-6 space-y-8">
                    ${tpl.question ? `
                        <div class="bg-amber-50 border-l-4 border-amber-400 p-4 rounded-r-lg">
                            <span class="text-xs font-bold text-amber-700 uppercase">Ví dụ đề bài:</span>
                            <p class="text-slate-700 italic mt-1">${tpl.question}</p>
                        </div>
                    ` : ''}

                    ${tpl.sections.map(section => `
                        <div class="border border-slate-100 rounded-xl bg-slate-50 overflow-hidden">
                            <div class="bg-slate-200/50 px-4 py-2 border-b border-slate-200 flex justify-between items-center">
                                <span class="font-bold text-slate-800">${section.name}</span>
                                ${section.description ? `<span class="text-xs text-slate-500 italic">${section.description}</span>` : ''}
                            </div>
                            <div class="p-4 space-y-4">
                                ${section.subsections ? section.subsections.map(sub => `
                                    <div>
                                        <h4 class="text-xs font-bold text-indigo-600 uppercase mb-2">${sub.label}</h4>
                                        <ul class="list-disc list-inside space-y-1 text-sm text-slate-700">
                                            ${sub.items.map(item => `<li>${item}</li>`).join('')}
                                        </ul>
                                    </div>
                                `).join('') : ''}
                                
                                ${section.sample ? `
                                    <div class="mt-4 p-3 bg-white border border-indigo-100 rounded-lg">
                                        <h4 class="text-xs font-bold text-emerald-600 uppercase mb-1">Sample Segment:</h4>
                                        <p class="text-slate-800 text-[13px] leading-relaxed italic">${section.sample}</p>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
    },

    renderTask1AcademicWords(containerId, unitId = 'ALL') {
        const container = document.getElementById(containerId);
        if (!container) return;

        let units = this.data.task1Words.units;
        if (!units) return;

        if (unitId !== 'ALL') {
            units = units.filter(u => u.id === unitId);
        }

        container.innerHTML = units.map(unit => `
            <div class="mb-12">
                <div class="flex items-center gap-3 mb-6 ${unit.color || 'bg-slate-800'} p-4 rounded-xl text-white shadow-lg">
                    <div class="p-2 bg-white/20 rounded-lg">
                        <i data-lucide="${unit.icon || 'book'}" class="w-6 h-6"></i>
                    </div>
                    <h3 class="text-2xl font-bold font-inter">${unit.title}</h3>
                </div>
                
                <div class="space-y-10">
                    ${unit.samples.map(sample => `
                        <div class="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden animate-fadeIn">
                             <div class="p-6 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
                                <h4 class="text-lg font-bold text-slate-800 flex items-center gap-2">
                                    <i data-lucide="file-text" class="w-5 h-5 text-indigo-600"></i> ${sample.title}
                                </h4>
                                ${sample.exam_note ? `<span class="text-xs text-slate-400 italic">${sample.exam_note}</span>` : ''}
                            </div>
                            <div class="p-6 space-y-6">
                                <div class="bg-slate-900 p-5 rounded-xl text-white">
                                    <p class="text-xs font-bold text-slate-400 uppercase mb-3">Bài mẫu (Sample):</p>
                                    <p class="text-slate-200 leading-relaxed font-serif italic whitespace-pre-line text-sm">${sample.sample_text}</p>
                                </div>
                                
                                <div>
                                    <p class="text-xs font-bold text-slate-400 uppercase mb-4">Cấu trúc nổi bật (Key Structures):</p>
                                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                                        ${(sample.vocab || sample.analysis || []).map((item, idx) => {
                                            const phrase = item.phrase || item.structure || '';
                                            const vi = item.vi || item.explanation || '';
                                            const exEn = item.example_en || item.example || '';
                                            const exVi = item.example_vi || '';
                                            return `
                                            <div class="p-4 bg-indigo-50 rounded-xl border border-indigo-100 hover:border-indigo-300 transition-colors">
                                                <div class="flex items-start gap-2 mb-2">
                                                    <span class="flex-shrink-0 w-5 h-5 bg-indigo-500 text-white text-[10px] font-black rounded-full flex items-center justify-center mt-0.5">${idx + 1}</span>
                                                    <code class="text-indigo-900 font-bold text-sm leading-snug">${phrase}</code>
                                                </div>
                                                <p class="text-xs text-slate-600 mb-3 leading-relaxed pl-7">${vi}</p>
                                                ${exEn ? `<div class="p-2 bg-white rounded-lg border border-indigo-100 text-[11px] pl-7">
                                                    <p class="text-slate-800 italic font-medium mb-1">${exEn}</p>
                                                    ${exVi ? `<p class="text-slate-400 italic">${exVi}</p>` : ''}
                                                </div>` : ''}
                                            </div>`;
                                        }).join('')}
                                    </div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `).join('');
        lucide.createIcons();
    },

    renderTask2IdeaBank(containerId, unitId = 'ALL') {
        const container = document.getElementById(containerId);
        if (!container) return;

        let units = this.data.task2Ideas.units;
        if (!units) return;

        if (unitId !== 'ALL') {
            units = units.filter(u => u.id === unitId);
        }

        container.innerHTML = `
            <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
                ${units.map(unit => `
                    <div class="bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden hover:shadow-xl transition-all duration-500 group animate-fadeIn">
                        <div class="h-2 bg-gradient-to-r from-indigo-500 to-purple-500"></div>
                        <div class="p-8">
                            <div class="flex items-center justify-between mb-6">
                                <div class="w-12 h-12 bg-indigo-50 rounded-2xl flex items-center justify-center text-indigo-600 group-hover:scale-110 transition-transform">
                                    <i data-lucide="lightbulb" class="w-6 h-6"></i>
                                </div>
                                <span class="text-[10px] font-bold text-slate-400 uppercase tracking-widest">${unit.id}</span>
                            </div>
                            
                            <h3 class="text-2xl font-bold text-slate-800 mb-6 group-hover:text-indigo-600 transition-colors">${unit.title}</h3>
                            
                            <div class="space-y-6">
                                <div>
                                    <p class="text-xs font-black text-slate-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                                        <i data-lucide="git-branch" class="w-3 h-3"></i> Brainstorming Ideas
                                    </p>
                                    <div class="space-y-4">
                                        ${unit.mind_map.map(map => `
                                            <div class="pl-4 border-l-2 border-indigo-100">
                                                <h4 class="text-sm font-bold text-indigo-900 mb-2">${map.category}</h4>
                                                <ul class="space-y-2">
                                                    ${map.points.map(pt => `
                                                        <li class="text-xs text-slate-600 flex items-start gap-2">
                                                            <span class="mt-1 w-1 h-1 bg-indigo-400 rounded-full flex-shrink-0"></span>
                                                            ${pt}
                                                        </li>
                                                    `).join('')}
                                                </ul>
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                                
                                <div class="pt-6 border-t border-slate-100">
                                    <p class="text-xs font-black text-slate-400 uppercase tracking-wider mb-3">Key Vocabulary</p>
                                    <div class="flex flex-wrap gap-2">
                                        ${unit.vocabulary.map(voc => `
                                            <div class="px-2 py-1 bg-slate-50 border border-slate-100 rounded text-[11px] group/item hover:bg-indigo-50 hover:border-indigo-100 transition-colors cursor-default">
                                                <span class="font-bold text-slate-700 group-hover/item:text-indigo-700">${voc.word}</span>
                                                <span class="text-slate-400 ml-1 italic">: ${voc.meaning}</span>
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
        lucide.createIcons();
    },

    renderReview(containerId, reviewKey = 'review2022', date = 'ALL', taskFilter = 'all') {
        const container = document.getElementById(containerId);
        if (!container) return;

        let exams = this.data[reviewKey]?.exams;
        if (!exams) return;

        if (date !== 'ALL') {
            exams = exams.filter(e => e.date === date);
        }

        const bandColor = (score) => {
            if (score >= 8) return 'bg-emerald-100 text-emerald-800';
            if (score >= 7) return 'bg-amber-100 text-amber-800';
            return 'bg-slate-100 text-slate-600';
        };

        const renderBand = (band) => {
            if (!band) return '';
            return `<div class="flex flex-wrap gap-1 mt-3">
                ${['TR','CC','LR','GRA'].map(k => `<span class="text-[10px] px-2 py-0.5 rounded font-bold ${bandColor(band[k])}">${k}: ${band[k]}</span>`).join('')}
                <span class="text-[10px] px-2 py-0.5 rounded font-black bg-indigo-600 text-white">Overall: ${band.overall}</span>
            </div>`;
        };

        const renderVocab = (vocab) => {
            if (!vocab || vocab.length === 0) return '';
            return `<div class="mt-3 flex flex-wrap gap-2">
                ${vocab.map(v => `<div class="text-[10px] bg-slate-50 border border-slate-200 rounded px-2 py-1">
                    <span class="font-bold text-indigo-700">${v.word}</span>
                    <span class="text-slate-400 italic"> – ${v.meaning}</span>
                </div>`).join('')}
            </div>`;
        };

        container.innerHTML = exams.map(exam => `
            <div class="mb-10 bg-white rounded-3xl border border-slate-200 shadow-xl overflow-hidden animate-fadeIn">
                <div class="bg-slate-900 text-white p-5 flex items-center justify-between">
                    <div>
                        <div class="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1 italic">ZIM · IELTS Writing Review (${reviewKey.replace('review', '')})</div>
                        <h3 class="text-2xl font-black font-inter">📅 ${exam.date}</h3>
                    </div>
                    <div class="px-4 py-2 bg-indigo-600 rounded-full text-xs font-bold shadow-lg">Exam Record</div>
                </div>
                
                <div class="grid grid-cols-1 ${taskFilter === 'all' ? 'lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x' : ''} divide-slate-100">
                    ${(taskFilter === 'all' || taskFilter === 'task1') ? `
                    <!-- Task 1 -->
                    <div class="p-6">
                        <div class="flex items-center gap-2 mb-3">
                            <div class="w-8 h-8 bg-amber-50 rounded-lg flex items-center justify-center text-amber-600">
                                <i data-lucide="bar-chart-2" class="w-4 h-4"></i>
                            </div>
                            <div>
                                <span class="text-xs font-black text-slate-400 uppercase">Writing Task 1</span>
                                ${exam.task_1.type ? `<span class="ml-2 text-[10px] bg-amber-100 text-amber-700 font-bold px-2 py-0.5 rounded">${exam.task_1.type}</span>` : ''}
                            </div>
                        </div>
                        <h4 class="text-base font-bold text-slate-800 mb-3">${exam.task_1.title}</h4>
                        
                        <div class="p-3 bg-slate-50 rounded-xl border border-slate-100 font-serif italic text-slate-600 text-xs mb-3">
                            "${exam.task_1.question}"
                        </div>
                        
                        <div class="space-y-2">
                            <div class="p-3 bg-indigo-50/60 rounded-xl border border-indigo-100/50">
                                <div class="text-[10px] font-bold text-indigo-400 uppercase mb-1">Overview</div>
                                <ul class="space-y-1">
                                    ${(Array.isArray(exam.task_1.overview) ? exam.task_1.overview : [exam.task_1.overview]).map(o => `<li class="text-xs text-indigo-900 font-medium">• ${o}</li>`).join('')}
                                </ul>
                            </div>
                            <div class="grid grid-cols-2 gap-2">
                                <div class="p-2 bg-white border border-slate-100 rounded-lg text-[11px] text-slate-600">
                                    <span class="font-bold text-slate-400 uppercase block mb-1">Thân bài 1</span>
                                    ${exam.task_1.body_1}
                                </div>
                                <div class="p-2 bg-white border border-slate-100 rounded-lg text-[11px] text-slate-600">
                                    <span class="font-bold text-slate-400 uppercase block mb-1">Thân bài 2</span>
                                    ${exam.task_1.body_2}
                                </div>
                            </div>
                        </div>
                        ${renderVocab(exam.task_1.key_vocab)}
                        ${renderBand(exam.task_1.band)}
                    </div>
                    ` : ''}
                    
                    ${(taskFilter === 'all' || taskFilter === 'task2') ? `
                    <!-- Task 2 -->
                    <div class="p-6 bg-slate-50/30">
                        <div class="flex items-center gap-2 mb-3">
                            <div class="w-8 h-8 bg-emerald-50 rounded-lg flex items-center justify-center text-emerald-600">
                                <i data-lucide="edit-3" class="w-4 h-4"></i>
                            </div>
                            <div>
                                <span class="text-xs font-black text-slate-400 uppercase">Writing Task 2</span>
                                ${exam.task_2.type ? `<span class="ml-2 text-[10px] bg-emerald-100 text-emerald-700 font-bold px-2 py-0.5 rounded">${exam.task_2.type}</span>` : ''}
                            </div>
                        </div>
                        <h4 class="text-base font-bold text-slate-800 mb-3">${exam.task_2.title}</h4>
                        
                        <div class="p-3 bg-white rounded-xl border border-slate-100 font-serif italic text-slate-600 text-xs mb-3 shadow-sm">
                            "${exam.task_2.question}"
                        </div>
                        
                        <div class="p-4 bg-emerald-50 rounded-xl border border-emerald-100 space-y-2">
                            ${exam.task_2.topic_vi ? `<p class="text-[10px] font-bold text-emerald-600 uppercase italic">${exam.task_2.topic_vi}</p>` : ''}
                            ${exam.task_2.view_1 ? `<div class="text-[11px] text-emerald-900 bg-white/70 p-2 rounded-lg border border-emerald-100"><strong class="text-emerald-600">View 1:</strong> ${exam.task_2.view_1}</div>` : ''}
                            ${exam.task_2.view_2 ? `<div class="text-[11px] text-emerald-900 bg-white/70 p-2 rounded-lg border border-emerald-100"><strong class="text-emerald-600">View 2:</strong> ${exam.task_2.view_2}</div>` : ''}
                            ${exam.task_2.opinion ? `<div class="text-[11px] text-emerald-900 bg-emerald-100 p-2 rounded-lg"><strong>✏️ Opinion:</strong> ${exam.task_2.opinion}</div>` : ''}
                        </div>
                        ${renderVocab(exam.task_2.key_vocab)}
                        ${renderBand(exam.task_2.band)}
                    </div>
                    ` : ''}
                </div>
            </div>
        `).join('');
        lucide.createIcons();
    },


    renderSimonGuide(containerId) {

        const container = document.getElementById(containerId);
        if (!container) return;

        const guide = this.data.simonGuide;
        if (!guide) return;

        container.innerHTML = `
            <div class="space-y-12 max-w-5xl mx-auto">
                <!-- Method Overview -->
                <div class="bg-indigo-900 rounded-3xl p-8 text-white shadow-2xl relative overflow-hidden">
                    <div class="absolute -right-10 -top-10 w-40 h-40 bg-indigo-500/20 rounded-full blur-3xl"></div>
                    <div class="relative z-10">
                        <div class="flex items-center gap-3 mb-6">
                            <span class="px-3 py-1 bg-indigo-500 rounded-full text-[10px] font-black uppercase tracking-widest shadow-lg">Simon's Collection</span>
                            <h3 class="text-3xl font-black font-inter tracking-tight">The 4-Paragraph Method</h3>
                        </div>
                        <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                            ${guide.method.structure.map((part, idx) => `
                                <div class="bg-white/10 backdrop-blur-md p-5 rounded-2xl border border-white/10 hover:bg-white/20 transition-all group">
                                    <div class="text-3xl font-black text-indigo-400 mb-2 group-hover:scale-110 transition-transform">0${idx + 1}</div>
                                    <h4 class="font-bold text-white mb-2 text-sm">${part.part}</h4>
                                    <p class="text-xs text-indigo-100 leading-relaxed">${part.description}</p>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>

                <!-- expert FAQ -->
                <div>
                    <div class="flex items-center gap-4 mb-8">
                        <div class="w-12 h-12 bg-white rounded-2xl flex items-center justify-center text-indigo-600 shadow-sm border border-slate-200">
                            <i data-lucide="help-circle" class="w-6 h-6"></i>
                        </div>
                        <div>
                            <h3 class="text-2xl font-black text-slate-800">Expert Q&A Hub</h3>
                            <p class="text-slate-500 text-sm italic">Simon answers common student questions</p>
                        </div>
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        ${guide.method.faq.map(item => `
                            <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:border-indigo-400 transition-colors group">
                                <h4 class="text-slate-800 font-bold mb-3 flex items-start gap-2">
                                    <span class="text-indigo-500 font-black">Q:</span>
                                    <span>${item.question}</span>
                                </h4>
                                <div class="bg-slate-50 p-4 rounded-xl text-xs text-slate-600 leading-relaxed border border-slate-100">
                                    <strong class="text-indigo-600 block mb-1 font-black uppercase tracking-tighter">Simon says:</strong>
                                    ${item.answer}
                                </div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        `;
        lucide.createIcons();
    }
};

// Global export for inline onclicks
window.IELTSPracticeHub = IELTSPracticeHub;
