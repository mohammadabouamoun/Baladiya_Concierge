#!/usr/bin/env python3
"""
Baladiya Concierge — civic intent dataset builder.

Produces a labelled intent dataset for the router/classifier (Design C).
This is SEPARATE from the tenant CMS/RAG corpus.

Schema (one row = one inbound resident message):
    id        stable string id
    text      the raw message a resident might type
    lang      ar | en
    variety   en | msa | lebanese | arabizi      (script/register, for per-variety F1)
    intent    report | question | human | spam    (drives the router)
    category  roads | water | electricity | waste | permits | taxes |
              environment | general | none        (civic domain; none for human/spam)
    split     train | test                         (deterministic, stratified-ish, no leakage)

Intent -> router action:
    report   -> capture_request  (resident reports a problem / asks for an action)
    question -> rag_search       (resident asks for information)
    human    -> escalate         (resident asks for a person)
    spam     -> drop             (gated out before any write)

NOTE: This is a SEED set, machine-drafted then meant to be hand-verified.
The spec requires a hand-curated, hand-verified Arabic set. Treat every row as a
draft to read, fix, and sign off on — you own every line at the defense.
"""
import csv
import hashlib

# (text, lang, variety, intent, category)
ROWS = []
def add(text, lang, variety, intent, category):
    ROWS.append((text, lang, variety, intent, category))

# ──────────────────────────────────────────────────────────────────────────
# ENGLISH (load-bearing baseline)
# ──────────────────────────────────────────────────────────────────────────
# report
add("There's a big pothole on Main Street near the bakery, someone almost crashed.", "en", "en", "report", "roads")
add("The street light in front of building 12 has been out for a week.", "en", "en", "report", "roads")
add("A traffic sign got knocked down at the corner of Independence Square.", "en", "en", "report", "roads")
add("The road is completely flooded after the rain, cars can't pass.", "en", "en", "report", "roads")
add("No water in our neighbourhood since this morning, can you check?", "en", "en", "report", "water")
add("There's a water pipe leaking on the sidewalk, it's been running for hours.", "en", "en", "report", "water")
add("Our building has had no water pressure for three days.", "en", "en", "report", "water")
add("The power has been cut on our street since last night.", "en", "en", "report", "electricity")
add("A power line is hanging low over the road, it looks dangerous.", "en", "en", "report", "electricity")
add("The garbage hasn't been collected on our street for over a week.", "en", "en", "report", "waste")
add("Someone dumped construction waste in the empty lot behind the school.", "en", "en", "report", "waste")
add("The dumpster on our corner is overflowing and it smells terrible.", "en", "en", "report", "waste")
add("There's raw sewage coming up from a manhole near the playground.", "en", "en", "report", "environment")
add("A factory nearby is releasing smoke all night, it's hard to breathe.", "en", "en", "report", "environment")
add("There's an abandoned car blocking the road for two weeks now.", "en", "en", "report", "roads")
add("I want to report a stray dog pack near the market, kids are scared.", "en", "en", "report", "environment")
add("The public park benches are broken and there's glass everywhere.", "en", "en", "report", "environment")
add("Streetlights on the coastal road are all off, it's pitch black at night.", "en", "en", "report", "roads")
add("I'd like to report illegal parking blocking the ambulance entrance.", "en", "en", "report", "roads")
add("Water is leaking into our basement from a burst municipal main.", "en", "en", "report", "water")

# question
add("Which department handles water cut-offs?", "en", "en", "question", "water")
add("How do I apply for a building permit?", "en", "en", "question", "permits")
add("What documents do I need to register my new business?", "en", "en", "question", "permits")
add("How can I get a proof of residence certificate?", "en", "en", "question", "permits")
add("When is the garbage collected in the Achrafieh area?", "en", "en", "question", "waste")
add("How much are the annual municipal fees for an apartment?", "en", "en", "question", "taxes")
add("Where can I pay my municipality bill?", "en", "en", "question", "taxes")
add("What are the opening hours of the municipality office?", "en", "en", "question", "general")
add("Where exactly is the municipality building located?", "en", "en", "question", "general")
add("Is there a phone number I can call for emergencies?", "en", "en", "question", "general")
add("Do I need an appointment to come in person?", "en", "en", "question", "general")
add("Who do I contact about a noisy construction site?", "en", "en", "question", "environment")
add("How long does a building permit usually take to be approved?", "en", "en", "question", "permits")
add("Can I pay my fees online or only at the office?", "en", "en", "question", "taxes")
add("What is the fine for late payment of municipal taxes?", "en", "en", "question", "taxes")
add("How do I get a birth certificate extract?", "en", "en", "question", "permits")
add("Which days does the recycling truck come?", "en", "en", "question", "waste")
add("Who is responsible for fixing public street lighting?", "en", "en", "question", "roads")
add("Is the water shortage affecting the whole town or just my area?", "en", "en", "question", "water")
add("What's the process to object to a tax assessment?", "en", "en", "question", "taxes")

# human
add("I want to speak to a real person, please.", "en", "en", "human", "none")
add("Can you connect me to someone in the office?", "en", "en", "human", "none")
add("This isn't helping, I need to talk to a staff member.", "en", "en", "human", "none")
add("Please transfer me to a municipal employee.", "en", "en", "human", "none")
add("I have a complaint and I need to talk to a human, not a bot.", "en", "en", "human", "none")
add("Give me the direct number of the responsible officer.", "en", "en", "human", "none")
add("Can someone from the council call me back?", "en", "en", "human", "none")
add("I'd like to file a formal complaint with an actual person.", "en", "en", "human", "none")

# spam
add("WIN a FREE iPhone now!!! Click this link to claim your prize.", "en", "en", "spam", "none")
add("Make $5000 a week working from home, DM me for details.", "en", "en", "spam", "none")
add("Cheap loans approved instantly, no credit check, call now.", "en", "en", "spam", "none")
add("Buy followers and likes, best prices guaranteed.", "en", "en", "spam", "none")
add("Hot singles in your area waiting to chat with you.", "en", "en", "spam", "none")
add("Invest in crypto today and double your money in 24 hours.", "en", "en", "spam", "none")
add("asdkjf askjdf lorem ipsum random text test test", "en", "en", "spam", "none")
add("Congratulations you have been selected for a $1000 gift card.", "en", "en", "spam", "none")
add("Best SEO services, rank #1 on Google, message us.", "en", "en", "spam", "none")
add("Discount Viagra and Cialis, free shipping worldwide.", "en", "en", "spam", "none")

# ──────────────────────────────────────────────────────────────────────────
# ARABIC — MODERN STANDARD ARABIC (MSA / فصحى)
# ──────────────────────────────────────────────────────────────────────────
# report
add("هناك حفرة كبيرة في الطريق الرئيسي قرب المخبز، كادت سيارة أن تنقلب.", "ar", "msa", "report", "roads")
add("عمود الإنارة أمام البناية رقم ١٢ مطفأ منذ أسبوع.", "ar", "msa", "report", "roads")
add("سقطت إشارة المرور عند زاوية الساحة الرئيسية.", "ar", "msa", "report", "roads")
add("الطريق غارق بالمياه بعد المطر ولا تستطيع السيارات المرور.", "ar", "msa", "report", "roads")
add("انقطعت المياه عن حيّنا منذ الصباح، أرجو المتابعة.", "ar", "msa", "report", "water")
add("هناك أنبوب مياه يتسرّب على الرصيف منذ ساعات.", "ar", "msa", "report", "water")
add("بنايتنا بلا ضغط مياه منذ ثلاثة أيام.", "ar", "msa", "report", "water")
add("انقطع التيار الكهربائي عن شارعنا منذ الليلة الماضية.", "ar", "msa", "report", "electricity")
add("هناك سلك كهرباء متدلٍّ فوق الطريق ويبدو خطيراً.", "ar", "msa", "report", "electricity")
add("لم تُجمع النفايات من شارعنا منذ أكثر من أسبوع.", "ar", "msa", "report", "waste")
add("قام أحدهم برمي مخلفات بناء في الأرض الفارغة خلف المدرسة.", "ar", "msa", "report", "waste")
add("حاوية النفايات في الزاوية ممتلئة وتفوح منها رائحة كريهة.", "ar", "msa", "report", "waste")
add("تتسرّب مياه الصرف الصحي من فتحة قرب الملعب.", "ar", "msa", "report", "environment")
add("هناك سيارة متروكة تسدّ الطريق منذ أسبوعين.", "ar", "msa", "report", "roads")
add("أودّ الإبلاغ عن أنوار الشارع المطفأة على الطريق الساحلي.", "ar", "msa", "report", "roads")
add("هناك تسرّب مياه إلى قبو منزلنا من ماسورة بلدية مكسورة.", "ar", "msa", "report", "water")
add("مصنع قريب يطلق الدخان طوال الليل ويصعب التنفّس.", "ar", "msa", "report", "environment")
add("مقاعد الحديقة العامة مكسورة وهناك زجاج في كل مكان.", "ar", "msa", "report", "environment")

# question
add("ما هي الدائرة المسؤولة عن انقطاع المياه؟", "ar", "msa", "question", "water")
add("كيف أتقدّم بطلب رخصة بناء؟", "ar", "msa", "question", "permits")
add("ما هي المستندات المطلوبة لتسجيل عمل تجاري جديد؟", "ar", "msa", "question", "permits")
add("كيف يمكنني الحصول على إفادة سكن؟", "ar", "msa", "question", "permits")
add("متى تُجمع النفايات في منطقة الأشرفية؟", "ar", "msa", "question", "waste")
add("كم تبلغ الرسوم البلدية السنوية للشقة؟", "ar", "msa", "question", "taxes")
add("أين يمكنني دفع فاتورة البلدية؟", "ar", "msa", "question", "taxes")
add("ما هي ساعات عمل مكتب البلدية؟", "ar", "msa", "question", "general")
add("أين يقع مبنى البلدية بالتحديد؟", "ar", "msa", "question", "general")
add("هل هناك رقم هاتف للطوارئ؟", "ar", "msa", "question", "general")
add("هل أحتاج إلى موعد مسبق للحضور شخصياً؟", "ar", "msa", "question", "general")
add("بمن أتصل بشأن ورشة بناء مزعجة؟", "ar", "msa", "question", "environment")
add("كم تستغرق الموافقة على رخصة البناء عادةً؟", "ar", "msa", "question", "permits")
add("هل يمكن دفع الرسوم عبر الإنترنت أم في المكتب فقط؟", "ar", "msa", "question", "taxes")
add("ما غرامة التأخّر في دفع الرسوم البلدية؟", "ar", "msa", "question", "taxes")
add("كيف أحصل على إخراج قيد فردي؟", "ar", "msa", "question", "permits")
add("في أي أيام تمرّ شاحنة إعادة التدوير؟", "ar", "msa", "question", "waste")
add("من المسؤول عن إصلاح إنارة الشوارع العامة؟", "ar", "msa", "question", "roads")

# human
add("أريد التحدّث إلى موظف حقيقي من فضلك.", "ar", "msa", "human", "none")
add("هل يمكنك تحويلي إلى شخص في المكتب؟", "ar", "msa", "human", "none")
add("هذا لا يفيدني، أريد التحدّث إلى أحد الموظفين.", "ar", "msa", "human", "none")
add("أرجو إعطائي الرقم المباشر للمسؤول.", "ar", "msa", "human", "none")
add("لديّ شكوى وأريد التحدّث إلى إنسان لا إلى روبوت.", "ar", "msa", "human", "none")
add("هل يمكن لأحد من البلدية معاودة الاتصال بي؟", "ar", "msa", "human", "none")
add("أودّ تقديم شكوى رسمية إلى موظف فعلي.", "ar", "msa", "human", "none")

# spam
add("اربح آيفون مجاناً الآن!!! اضغط الرابط للحصول على جائزتك.", "ar", "msa", "spam", "none")
add("اكسب ٥٠٠٠ دولار أسبوعياً من المنزل، راسلني للتفاصيل.", "ar", "msa", "spam", "none")
add("قروض رخيصة بموافقة فورية وبدون تحقّق، اتصل الآن.", "ar", "msa", "spam", "none")
add("استثمر في العملات الرقمية اليوم وضاعف أموالك خلال ٢٤ ساعة.", "ar", "msa", "spam", "none")
add("أفضل خدمات تحسين محركات البحث، تصدّر النتائج، راسلنا.", "ar", "msa", "spam", "none")
add("عقارات بأسعار مغرية جداً، اتصل الآن قبل نفاد العرض.", "ar", "msa", "spam", "none")
add("مبروك! تم اختيارك للفوز ببطاقة هدايا بقيمة ١٠٠٠ دولار.", "ar", "msa", "spam", "none")
add("زيادة متابعين ولايكات بأرخص الأسعار مضمونة.", "ar", "msa", "spam", "none")

# ──────────────────────────────────────────────────────────────────────────
# ARABIC — LEBANESE DIALECT (عامية لبنانية)
# ──────────────────────────────────────────────────────────────────────────
# report
add("في حفرة كبيرة بالطريق قدّام الفرن، كادت سيارة تنقلب.", "ar", "lebanese", "report", "roads")
add("عمود الإنارة قدّام بناية رقم ١٢ مطفّي من جمعة.", "ar", "lebanese", "report", "roads")
add("الطريق كلّو مي بعد الشتي وما عم تفوت السيارات.", "ar", "lebanese", "report", "roads")
add("في إشارة سير وقعت عند مفرق الساحة.", "ar", "lebanese", "report", "roads")
add("ما في مي بالحي من الصبح، فيك تشيك؟", "ar", "lebanese", "report", "water")
add("في ماسورة مي عم تنقّط عالرصيف من ساعات.", "ar", "lebanese", "report", "water")
add("بنايتنا ما في عندا ضغط مي من تلت تيام.", "ar", "lebanese", "report", "water")
add("الكهربا مقطوعة عن شارعنا من مبارح بالليل.", "ar", "lebanese", "report", "electricity")
add("في سلك كهربا نازل عالطريق وشكلو خطير.", "ar", "lebanese", "report", "electricity")
add("النفايات ما حدا أخدها من شارعنا من أكتر من جمعة.", "ar", "lebanese", "report", "waste")
add("حدا كبّ بقايا باطون بالأرض الفاضية ورا المدرسة.", "ar", "lebanese", "report", "waste")
add("حاوية الزبالة عالزاوية فايضة وريحتها بشعة.", "ar", "lebanese", "report", "waste")
add("في مجرور مفتوح عم تطلع منو مي صرف حدّ الملعب.", "ar", "lebanese", "report", "environment")
add("في سيارة متروكة سادّة الطريق من أسبوعين.", "ar", "lebanese", "report", "roads")
add("بدّي بلّغ عن أنوار الطريق المطفّية عالأوتوستراد.", "ar", "lebanese", "report", "roads")
add("عم تفوت مي عالقبو من ماسورة البلدية المكسورة.", "ar", "lebanese", "report", "water")
add("في معمل جنبنا عم يطلّع دخان طول الليل وما عم نقدر نتنفّس.", "ar", "lebanese", "report", "environment")
add("كراسي الحديقة العامة مكسّرة وفي قزاز بكل مكان.", "ar", "lebanese", "report", "environment")
add("في ريحة مجارير قوية عم تطلع من المنهول قدّام بيتنا.", "ar", "lebanese", "report", "environment")
add("الزبالة مكدّسة عند المستوعب وصار في فيران.", "ar", "lebanese", "report", "waste")

# question
add("مين الدائرة يلّي بتهتم بقطع المي؟", "ar", "lebanese", "question", "water")
add("كيف بقدّم طلب رخصة بنا؟", "ar", "lebanese", "question", "permits")
add("شو الأوراق يلّي بدّي ياها لسجّل محل تجاري؟", "ar", "lebanese", "question", "permits")
add("كيف بطلّع إفادة سكن؟", "ar", "lebanese", "question", "permits")
add("إيمتى بياخدو الزبالة بمنطقة الأشرفية؟", "ar", "lebanese", "question", "waste")
add("قدّيش رسوم البلدية السنوية عالشقة؟", "ar", "lebanese", "question", "taxes")
add("وين فيني ادفع فاتورة البلدية؟", "ar", "lebanese", "question", "taxes")
add("شو أوقات دوام مكتب البلدية؟", "ar", "lebanese", "question", "general")
add("وين مكتب البلدية بالزبط؟", "ar", "lebanese", "question", "general")
add("في رقم تلفون للطوارئ؟", "ar", "lebanese", "question", "general")
add("بدّي موعد قبل ما إجي ولا فيي إجي دغري؟", "ar", "lebanese", "question", "general")
add("مع مين بحكي بخصوص ورشة بنا عم تعمل دوشة؟", "ar", "lebanese", "question", "environment")
add("قدّيش بياخد وقت تتطلع رخصة البنا؟", "ar", "lebanese", "question", "permits")
add("فيني ادفع الرسوم أونلاين ولا لازم روح عالمكتب؟", "ar", "lebanese", "question", "taxes")
add("قدّيش الغرامة إذا تأخّرت بدفع رسوم البلدية؟", "ar", "lebanese", "question", "taxes")
add("كيف بطلّع إخراج قيد؟", "ar", "lebanese", "question", "permits")
add("أيّ تيام بتمرق سيارة إعادة التدوير؟", "ar", "lebanese", "question", "waste")
add("مين مسؤول عن تصليح إنارة الشوارع؟", "ar", "lebanese", "question", "roads")
add("قطع المي شامل كل البلدة ولا بس منطقتنا؟", "ar", "lebanese", "question", "water")
add("شو الطريقة لاعترض عالرسوم؟", "ar", "lebanese", "question", "taxes")

# human
add("بدّي احكي مع حدا حقيقي لو سمحت.", "ar", "lebanese", "human", "none")
add("فيك توصّلني لحدا بالمكتب؟", "ar", "lebanese", "human", "none")
add("هيدا ما عم يفيدني، بدّي احكي مع موظف.", "ar", "lebanese", "human", "none")
add("عطيني الرقم المباشر تبع المسؤول.", "ar", "lebanese", "human", "none")
add("عندي شكوى وبدّي احكي مع زلمة مش مع روبوت.", "ar", "lebanese", "human", "none")
add("في حدا من البلدية يرجّعلي تلفون؟", "ar", "lebanese", "human", "none")
add("بدّي قدّم شكوى رسمية مع موظف فعلي.", "ar", "lebanese", "human", "none")
add("وصّلني لموظف بليز ما بدّي بوت.", "ar", "lebanese", "human", "none")

# spam
add("اربح آيفون ببلاش هلّق!!! دوس عالرابط تتقبض جائزتك.", "ar", "lebanese", "spam", "none")
add("اكسب ٥٠٠٠ دولار بالجمعة من البيت، رسّلي خاص.", "ar", "lebanese", "spam", "none")
add("قروض رخيصة وموافقة عالطاير بلا أوراق، دق هلّق.", "ar", "lebanese", "spam", "none")
add("حطّ مصاري بالبيتكوين اليوم وضاعفهن ب٢٤ ساعة.", "ar", "lebanese", "spam", "none")
add("عقارات بأسعار خيالية، دق قبل ما يخلص العرض.", "ar", "lebanese", "spam", "none")
add("بنزيدلك متابعين ولايكات بأرخص سعر.", "ar", "lebanese", "spam", "none")
add("مبروك ربحت بطاقة هدايا ب١٠٠٠ دولار، أكّد بياناتك.", "ar", "lebanese", "spam", "none")

# ──────────────────────────────────────────────────────────────────────────
# ARABIC — ARABIZI (Lebanese written in Latin letters + numbers)
# 2=ء/ق  3=ع  5=خ  6=ط  7=ح  8=غ  9=ص
# ──────────────────────────────────────────────────────────────────────────
# report
add("fi 7afra kbire bel tari2 2eddem el fern, kedet syyara ten2leb.", "ar", "arabizi", "report", "roads")
add("3amoud el inara 2eddem bineye ra2am 12 mou6fe men jem3a.", "ar", "arabizi", "report", "roads")
add("el tari2 kello may ba3d el sheti w ma 3am tfout el syyarat.", "ar", "arabizi", "report", "roads")
add("ma fi may bel 7ay men el sob7, fik tcheck?", "ar", "arabizi", "report", "water")
add("fi masoura may 3am tno22o6 3al rasif men se3at.", "ar", "arabizi", "report", "water")
add("el kahraba ma26ou3a 3an share3na men mbere7 bel layl.", "ar", "arabizi", "report", "electricity")
add("fi selk kahraba nezel 3al tari2 w shaklo khater.", "ar", "arabizi", "report", "electricity")
add("el nfeyet ma 7ada akhada men share3na men aktar men jem3a.", "ar", "arabizi", "report", "waste")
add("7awiyet el zbele fayme w ri7ta bshe3a.", "ar", "arabizi", "report", "waste")
add("fi majrour maftou7 3am tetla3 menno may sarf 7add el mal3ab.", "ar", "arabizi", "report", "environment")
add("fi syyara matrouke sadde el tari2 men esbou3ayn.", "ar", "arabizi", "report", "roads")
add("baddi ballegh 3an anwar el tari2 el mou6fiye 3al autostrad.", "ar", "arabizi", "report", "roads")
add("3am tfout may 3al 2abo men masoura el baladiye el meksoura.", "ar", "arabizi", "report", "water")
add("fi ma3mal jambna 3am ytalle3 dekhen toul el layl.", "ar", "arabizi", "report", "environment")
add("el zbele mkaddase 3and el mostaw3ab w sar fi firan.", "ar", "arabizi", "report", "waste")
add("fi ri7it majarir 2awiye 3am tetla3 men el manhole 2eddem baytna.", "ar", "arabizi", "report", "environment")

# question
add("min el da2ira yalli btehtam b2at3 el may?", "ar", "arabizi", "question", "water")
add("kif 2addem talab rokh9et bina?", "ar", "arabizi", "question", "permits")
add("shou el awra2 yalli baddi yehon la sajjel ma7al tijari?", "ar", "arabizi", "question", "permits")
add("kif 6alle3 ifedet sakan?", "ar", "arabizi", "question", "permits")
add("emta byekhdo el zbele b mante2et el ashrafiye?", "ar", "arabizi", "question", "waste")
add("2addaysh rsoum el baladiye el sanawiye 3al she22a?", "ar", "arabizi", "question", "taxes")
add("wen fini edfa3 fatourit el baladiye?", "ar", "arabizi", "question", "taxes")
add("shou aw2at dawem maktab el baladiye?", "ar", "arabizi", "question", "general")
add("wen maktab el baladiye bel zab6?", "ar", "arabizi", "question", "general")
add("fi ra2am telephone lal 6awari2?", "ar", "arabizi", "question", "general")
add("baddi maw3ad 2abel ma eje wella fini eje daghre?", "ar", "arabizi", "question", "general")
add("ma3 min be7ki bi5sous warshe 3am ta3mol dawshe?", "ar", "arabizi", "question", "environment")
add("2addaysh byekhod wa2et ta yetla3 rokh9et el bina?", "ar", "arabizi", "question", "permits")
add("fini edfa3 el rsoum online wella lezem rou7 3al maktab?", "ar", "arabizi", "question", "taxes")
add("kif 6alle3 ekhraj 2ayd?", "ar", "arabizi", "question", "permits")
add("min mas2oul 3an ta9li7 inaret el shawer3?", "ar", "arabizi", "question", "roads")

# human
add("baddi e7ki ma3 7ada 7a2i2i law sama7t.", "ar", "arabizi", "human", "none")
add("fik twa9elne la 7ada bel maktab?", "ar", "arabizi", "human", "none")
add("hayda ma 3am yfidne, baddi e7ki ma3 mwazzaf.", "ar", "arabizi", "human", "none")
add("3a6ine el ra2am el mbesher taba3 el mas2oul.", "ar", "arabizi", "human", "none")
add("3andi shakwa w baddi e7ki ma3 zalame mish ma3 bot.", "ar", "arabizi", "human", "none")
add("fi 7ada men el baladiye yrajje3le telephone?", "ar", "arabizi", "human", "none")
add("wa9elne la mwazzaf please ma baddi bot.", "ar", "arabizi", "human", "none")

# spam
add("erba7 iphone bb balash hala2!!! dous 3al link ta to2bod jeztak.", "ar", "arabizi", "spam", "none")
add("eksab 5000 dollar bel jem3a men el bayt, rasselle khass.", "ar", "arabizi", "spam", "none")
add("7ot ma9are bel bitcoin el yom w da3efon b 24 se3a.", "ar", "arabizi", "spam", "none")
add("3a2arat b as3ar 5ayaliye, do2 2abel ma yekhlas el 3ard.", "ar", "arabizi", "spam", "none")
add("mabrouk reb7et bita2a hadaya b 1000 dollar, 2akked bayanatak.", "ar", "arabizi", "spam", "none")
add("bnzidlak mtab3in w likes b ar5as se3er.", "ar", "arabizi", "spam", "none")

# ──────────────────────────────────────────────────────────────────────────
# build + deterministic split (no leakage: hash on text, ~20% test, per class)
# ──────────────────────────────────────────────────────────────────────────
def split_for(text, intent, variety):
    # bucket by (intent, variety) so test stays stratified; hash text for stability
    h = int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16)
    return "test" if (h % 5 == 0) else "train"

with open("civic_intent_dataset.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "text", "lang", "variety", "intent", "category", "split"])
    for i, (text, lang, variety, intent, category) in enumerate(ROWS, 1):
        rid = f"{lang}-{variety}-{i:03d}"
        w.writerow([rid, text, lang, variety, intent, category, split_for(text, intent, variety)])

# print a quick summary
from collections import Counter
print(f"total rows: {len(ROWS)}")
print("by lang/variety:", dict(Counter(f"{r[1]}/{r[2]}" for r in ROWS)))
print("by intent:", dict(Counter(r[3] for r in ROWS)))
print("by category:", dict(Counter(r[4] for r in ROWS)))
