# حزمة التجربة الاستطلاعية (Pilot Kit)

> **حالة الاختبار:** منطق التنفيذ (التوليد ← الإصلاح بالذراعين ← التقييم ← الاستئناف ← التحليل ← المحاكاة) مُختبَر على نموذج **وهمي** ومهام اصطناعية.
> **غير مُختبَر:** أي نموذج حقيقي، و`crosshair_verify`، و`make_tasks_evalplus.py` (يحتاجان تثبيت الحزم والإنترنت، وهما غير متاحين في بيئتي).
> ملفات `DEMO_*` و`demo_*` أرقامها بلا معنى علمي، وللتحقق من السباكة فقط.

## 1) التثبيت (على جهازك)
```bash
pip install crosshair-tool evalplus
# نموذج محلي (مثال: CPU يكفي لنماذج 1.5B؛ اختر ما يناسب عتادك وتحقق من توفره):
ollama pull qwen2.5-coder:1.5b        # نموذج مولّد A (مثال)
ollama pull <نموذج من عائلة أخرى>      # مولّد B
ollama pull <نموذج ثالث>               # C: مولّد المواصفات فقط
```
بدل Ollama يمكنك تشغيل خادم llama.cpp ثم: `export OPENAI_BASE_URL=http://localhost:8080/v1` واستخدام `openai:<اسم>`.

## 2) اختبار CrossHair أولاً (إلزامي)
```bash
python core.py --selftest
```
المتوقع: `good -> PASS` (أو UNKNOWN) و`bad -> FAIL` مع مثال مضاد. إن اختلفت المخرجات فعدّل تحليل المخرجات داخل `crosshair_verify` قبل أي شيء.

## 3) توليد مهام الـ pilot (40 مهمة من HumanEval+)
```bash
python make_tasks_evalplus.py --n 40 --seed 2026 --out pilot_tasks.jsonl
```
احفظ قائمة المعرّفات المطبوعة: **تُستبعد من العينة التأكيدية**.

## 4) التشغيل (قابل للاستئناف إن انقطع)
```bash
python run_pilot.py --tasks pilot_tasks.jsonl --n-tasks 40 \
  --gen-models ollama:MODEL_A,ollama:MODEL_B --spec-model ollama:MODEL_C \
  --verifier crosshair --gens 3 --rounds 2 --out traces.jsonl
```

## 5) التحليل ثم المحاكاة
```bash
python analyze.py traces.jsonl            # يكتب pilot_summary.json
python power_from_pilot.py pilot_summary.json
```
أرسل لي `traces.jsonl` و`pilot_summary.json` وأبني معك الأقسام 5.6 و6 والملحق C من نتائجك الحقيقية.

## تحذيرات مهمة
1. **التنفيذ ليس sandbox حقيقياً:** الكود المولَّد يعمل في subprocess بمهلة فقط. شغّله داخل حاوية/جهاز افتراضي قابل للحذف.
2. **أسئلة الاختبار العامة تقريبية:** المحوّل يأخذ أول 3 مدخلات base كاختبارات "عامة"، والتصميم الحقيقي يجب أن يستخرج أمثلة docstring. لا تعتمد على أرقام a_t كما هي.
3. **ثغرة محتملة في تصميمك (تحقق منها):** مهام MBPP+ لا تحمل تلميحات أنواع في الـ prompt على حد علمي، وCrossHair لا يولّد مدخلات بدونها (فتصنَّف UNSUPPORTED). فإن صح ذلك فالتغطية في MBPP+ قد تقارب الصفر، وهذا يهدد افتراض التغطية 0.5–0.8. قس ذلك في الـ pilot بنفسك.
4. **قاعدة الإصلاح:** لا يُستدعى الإصلاح في ذراع Verification إلا عند FAIL، وفي ذراع Test إلا عند فشل اختبار عام. هذه القاعدة المطلوبة في نقطة 4 من مراجعتي، وثبّتها في الورقة قبل التشغيل.
5. **لا تعدّل التصميم بعد رؤية النتائج** إلا بتوثيقها كانحراف عن البروتوكول.
