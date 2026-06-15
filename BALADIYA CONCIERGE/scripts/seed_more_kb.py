"""Seed additional KB entries for the Beirut demo tenant.

Run inside the api container (has app code, Vault env, embedding client):
    docker compose exec -T api python - < scripts/seed_more_kb.py

Idempotency: skips any entry whose title already exists for the tenant.
Each entry is chunked and embedded via gemini-embedding-001 (separate quota
from chat generation, so it works even while chat is rate-limited).
"""
import asyncio
import os
import uuid

from sqlalchemy import text

from api.core.config import get_settings
from api.infra.db import init_db, get_session_factory
import api.domain.tenant  # noqa: F401  — register tenants table for FK resolution
from api.infra import embedding_client as emb
from api.services import cms_service
from api.repositories.cms_repo import CmsEntryRepository
from api.domain.cms import CmsEntryCreate

TENANT_ID = "4667fd7f-944b-4ea8-bf07-657cf4b4b880"  # Beirut Municipality

ENTRIES: list[CmsEntryCreate] = [
    # ── English ──────────────────────────────────────────────────────────
    CmsEntryCreate(category="environment", lang="en", title="Public Parks and Gardens",
        body="The municipality maintains 12 public parks and gardens. Opening hours are 6:00 AM to 10:00 PM daily, closing at sunset in winter. Entry is free. Dogs must be kept on a leash and owners must clean up after their pets. Barbecues and open fires are only allowed in designated picnic zones and require a free permit obtained at baladiya.gov/parks or by calling 1700. Cycling is permitted on marked paths only. To report damaged equipment or request maintenance, call 1700 or submit a report online."),
    CmsEntryCreate(category="general", lang="en", title="Noise Complaints and Quiet Hours",
        body="Quiet hours in residential areas are 10:00 PM to 7:00 AM on weekdays and 11:00 PM to 8:00 AM on weekends. Construction noise is prohibited before 7:00 AM and after 6:00 PM. To report a noise violation, call the municipal hotline 1700 during office hours, or the 24/7 line 1711 for ongoing late-night disturbances. Provide the address, time, and nature of the noise. Repeat violations may result in a fine of 250,000 LBP."),
    CmsEntryCreate(category="general", lang="en", title="Dog and Pet Licensing",
        body="All dogs over four months old must be licensed with the municipality. To register, submit Form PL-09 with proof of rabies vaccination and one photo of the animal. The annual licence fee is 75,000 LBP, or 37,500 LBP for spayed or neutered animals. Licences are renewed every January. Apply at the Veterinary Services desk in Room 108 of the Municipal Building, or online at baladiya.gov/pets. A lost pet tag can be replaced for 15,000 LBP."),
    CmsEntryCreate(category="permits", lang="en", title="Business Licensing",
        body="To operate a commercial business you must obtain a municipal business licence. Submit Form BL-03 along with your commercial registration, your lease agreement or property deed, and an approved health and safety inspection certificate (required for food businesses). The annual licence fee depends on the business category and ranges from 400,000 to 2,500,000 LBP. Processing takes 10 working days. Licences must be renewed before March 31 each year. Contact the Licensing Department at 1700 or licensing@municipality.lb."),
    CmsEntryCreate(category="roads", lang="en", title="Residential Parking Permits",
        body="Residents in designated zones may apply for a residential parking permit. Submit Form RP-05 with proof of residence such as a utility bill, plus your vehicle registration. The permit costs 120,000 LBP per year and allows parking in your zone's blue-marked spaces without time limits. Each household may hold up to two permits. Visitor parking scratch-cards are available for 5,000 LBP per day. Apply online at baladiya.gov/parking or at Room 203 of the Municipal Building."),
    CmsEntryCreate(category="waste", lang="en", title="Street Cleaning Schedule",
        body="Mechanical street sweeping runs overnight from 11:00 PM to 5:00 AM. Main avenues are swept nightly. Residential streets are swept twice weekly: Mondays and Thursdays in the eastern district, and Tuesdays and Fridays in the western district. On your street's sweeping night, move vehicles off the marked side so the sweeper can pass; vehicles blocking the sweeper may be ticketed. To request additional cleaning after an event or spill, call 1700."),
    CmsEntryCreate(category="water", lang="en", title="New Water Connection",
        body="To request a new water connection or meter, submit Form WC-02 with your property deed, building permit number, and a site plan. The connection fee is 600,000 LBP for residential properties and 1,500,000 LBP for commercial properties, plus a refundable meter deposit of 200,000 LBP. Installation is scheduled within 15 working days of approval. For connection enquiries, contact the Water Department at 1700 or visit the office between 8 AM and 3 PM on weekdays."),
    CmsEntryCreate(category="environment", lang="en", title="Stray Animal Control",
        body="To report a stray or injured animal, call the Animal Control unit at 1700 during office hours, or 1711 after hours for emergencies involving aggressive animals. Provide the location and a description of the animal. The municipality operates a humane catch-and-release programme for stray cats and rehomes dogs through partner shelters. Do not attempt to handle aggressive or injured animals yourself. Reports are typically responded to within 24 hours."),
    CmsEntryCreate(category="environment", lang="en", title="Tree Planting and Landscaping Requests",
        body="Residents may request the planting of a street tree in front of their property, or report a dangerous or dead tree on public land. Submit a request online at baladiya.gov/greening or call 1700. The municipality plants approved native species during the autumn planting season from October to December. Pruning of public trees is handled by the Parks Department. Do not prune or remove public trees yourself, as this carries a fine of 500,000 LBP."),
    CmsEntryCreate(category="general", lang="en", title="Public Hall and Venue Booking",
        body="The municipality rents three public halls for community events, weddings, and meetings, with capacities from 80 to 400 guests. To book, submit Form VH-07 at least 21 days in advance with a refundable deposit. Rental rates range from 300,000 LBP for the small hall to 1,200,000 LBP for the main hall per day, with a 50% discount for registered non-profit and community groups. Check availability and book at baladiya.gov/halls or call 1700, extension 4."),
    # ── Arabic ───────────────────────────────────────────────────────────
    CmsEntryCreate(category="environment", lang="ar", title="الحدائق والمنتزهات العامة",
        body="تُشرف البلدية على 12 حديقة ومنتزهاً عاماً. ساعات العمل من السادسة صباحاً حتى العاشرة مساءً يومياً، وتُغلق عند الغروب في فصل الشتاء. الدخول مجاني. يجب إبقاء الكلاب مربوطة وتنظيف فضلاتها. لا يُسمح بالشواء وإشعال النار إلا في المناطق المخصّصة وبموجب تصريح مجاني يُطلب عبر baladiya.gov أو بالاتصال على 1700. لركوب الدراجات استخدم المسارات المخصّصة فقط. للإبلاغ عن أضرار أو طلب صيانة اتصل على 1700."),
    CmsEntryCreate(category="general", lang="ar", title="شكاوى الضجيج وساعات الهدوء",
        body="ساعات الهدوء في المناطق السكنية من العاشرة مساءً حتى السابعة صباحاً في أيام الأسبوع، ومن الحادية عشرة مساءً حتى الثامنة صباحاً في عطلة نهاية الأسبوع. يُمنع ضجيج البناء قبل السابعة صباحاً وبعد السادسة مساءً. للإبلاغ عن مخالفة ضجيج اتصل على الخط البلدي 1700 خلال أوقات العمل، أو على الخط 1711 على مدار الساعة للإزعاج الليلي المستمر. حدّد العنوان والوقت ونوع الضجيج. قد تؤدي المخالفات المتكررة إلى غرامة 250,000 ليرة."),
    CmsEntryCreate(category="permits", lang="ar", title="رخصة العمل التجاري",
        body="لمزاولة نشاط تجاري يجب الحصول على رخصة عمل بلدية. قدّم النموذج BL-03 مع السجل التجاري وعقد الإيجار أو سند الملكية وشهادة فحص صحة وسلامة معتمدة (إلزامية لمحلات الأطعمة). تتراوح رسوم الرخصة بحسب فئة النشاط بين 400,000 و2,500,000 ليرة سنوياً. تستغرق المعاملة 10 أيام عمل. تُجدَّد الرخصة قبل 31 آذار من كل عام. للتواصل مع دائرة الرخص اتصل على 1700 أو licensing@municipality.lb."),
    CmsEntryCreate(category="water", lang="ar", title="طلب اشتراك مياه جديد",
        body="لطلب اشتراك مياه جديد أو عدّاد، قدّم النموذج WC-02 مع سند ملكية العقار ورقم رخصة البناء ومخطط الموقع. رسم التوصيل 600,000 ليرة للعقارات السكنية و1,500,000 ليرة للعقارات التجارية، إضافةً إلى تأمين عدّاد قابل للاسترداد قدره 200,000 ليرة. يتم التركيب خلال 15 يوم عمل من الموافقة. للاستفسار اتصل بدائرة المياه على 1700 أو زر المكتب بين الثامنة صباحاً والثالثة مساءً في أيام العمل."),
    CmsEntryCreate(category="general", lang="ar", title="ترخيص الحيوانات الأليفة",
        body="يجب ترخيص جميع الكلاب التي تتجاوز أربعة أشهر لدى البلدية. للتسجيل قدّم النموذج PL-09 مع إثبات تطعيم ضد داء الكلب وصورة للحيوان. رسم الترخيص السنوي 75,000 ليرة، أو 37,500 ليرة للحيوانات المعقّمة. يُجدَّد الترخيص كل كانون الثاني. تقدّم بالطلب لدى مكتب الخدمات البيطرية في الغرفة 108، أو عبر baladiya.gov. يمكن استبدال بطاقة حيوان مفقودة مقابل 15,000 ليرة."),
    CmsEntryCreate(category="roads", lang="ar", title="تصاريح وقوف السيارات للمقيمين",
        body="يحق للمقيمين في المناطق المخصّصة التقدّم بطلب تصريح وقوف سيارة للمقيمين. قدّم النموذج RP-05 مع إثبات إقامة مثل فاتورة خدمات، إضافةً إلى أوراق تسجيل المركبة. كلفة التصريح 120,000 ليرة سنوياً ويتيح الوقوف في المواقف ذات العلامات الزرقاء ضمن منطقتك دون قيود زمنية. يحق لكل أسرة الحصول على تصريحين كحدّ أقصى. تتوفّر بطاقات وقوف للزوار مقابل 5,000 ليرة في اليوم. تقدّم بالطلب عبر baladiya.gov أو في الغرفة 203 من مبنى البلدية."),
    CmsEntryCreate(category="waste", lang="ar", title="جدول تنظيف الشوارع",
        body="يجري الكنس الآلي للشوارع ليلاً من الحادية عشرة مساءً حتى الخامسة صباحاً. تُكنس الشوارع الرئيسية كل ليلة. أمّا الشوارع السكنية فتُكنس مرّتين أسبوعياً: الإثنين والخميس في المنطقة الشرقية، والثلاثاء والجمعة في المنطقة الغربية. في ليلة كنس شارعك، انقل سيارتك عن الجهة ذات العلامة لتمرّ آلة الكنس؛ وقد تُغرَّم المركبات التي تعيق الآلة. لطلب تنظيف إضافي بعد حدث أو انسكاب اتصل على 1700."),
    CmsEntryCreate(category="environment", lang="ar", title="مكافحة الحيوانات الشاردة",
        body="للإبلاغ عن حيوان شارد أو مصاب، اتصل بوحدة مكافحة الحيوانات على 1700 خلال أوقات العمل، أو على 1711 خارج أوقات العمل للحالات الطارئة المتعلّقة بحيوانات عدوانية. حدّد الموقع وصف الحيوان. تُشغّل البلدية برنامجاً إنسانياً للإمساك بالقطط الشاردة وإطلاقها، وتعيد إيواء الكلاب عبر ملاجئ شريكة. لا تحاول التعامل بنفسك مع حيوانات عدوانية أو مصابة. تُعالَج البلاغات عادةً خلال 24 ساعة."),
    CmsEntryCreate(category="environment", lang="ar", title="طلبات زراعة الأشجار وتنسيق الحدائق",
        body="يحق للمقيمين طلب زراعة شجرة على الرصيف أمام عقاراتهم، أو الإبلاغ عن شجرة خطرة أو ميتة على أرض عامة. قدّم الطلب عبر baladiya.gov أو بالاتصال على 1700. تزرع البلدية الأنواع المحلية المعتمدة خلال موسم الزراعة الخريفي من تشرين الأول حتى كانون الأول. تتولّى دائرة الحدائق تقليم الأشجار العامة. لا تقم بتقليم أو إزالة الأشجار العامة بنفسك، فهذا يعرّضك لغرامة قدرها 500,000 ليرة."),
    CmsEntryCreate(category="general", lang="ar", title="حجز القاعات والصالات العامة",
        body="تؤجّر البلدية ثلاث قاعات عامة للمناسبات المجتمعية والأعراس والاجتماعات، تتّسع من 80 إلى 400 شخص. للحجز، قدّم النموذج VH-07 قبل 21 يوماً على الأقل مع تأمين قابل للاسترداد. تتراوح أجور الإيجار بين 300,000 ليرة للقاعة الصغيرة و1,200,000 ليرة للقاعة الكبرى في اليوم، مع حسم 50% للجمعيات غير الربحية والمجموعات المجتمعية المسجّلة. تحقّق من التوافر واحجز عبر baladiya.gov أو بالاتصال على 1700، المقسّم 4."),
]


async def main() -> None:
    settings = get_settings()
    db_url = getattr(settings, "database_url", None) or os.environ["DATABASE_URL"]
    await init_db(db_url)
    await emb.init_embedding_client()

    tenant = uuid.UUID(TENANT_ID)
    factory = get_session_factory()
    created = skipped = failed = 0

    async with factory() as session:
        await session.execute(text(f"SET app.current_tenant = '{TENANT_ID}'"))
        repo = CmsEntryRepository(session, tenant)
        existing = {e.title for e in await repo.list_entries()}

        for payload in ENTRIES:
            if payload.title in existing:
                print(f"  skip (exists)  {payload.lang} / {payload.category} — {payload.title}")
                skipped += 1
                continue
            entry = await cms_service.create_entry(session, tenant, payload)
            status = entry.embedding_status
            print(f"  [{status}]  {entry.lang} / {entry.category} — {entry.title}")
            if status == "done":
                created += 1
            else:
                failed += 1

        await session.execute(text("RESET app.current_tenant"))

    await emb.close_embedding_client()
    print(f"\nDone. created={created} skipped={skipped} failed={failed}")


asyncio.run(main())
