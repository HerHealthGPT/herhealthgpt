import type { ArticleMessages, DashboardMessages } from "../en/dashboard";

/** Arabic plurals have more than two forms; these cover the counts shown here. */
function consultations(count: number): string {
  if (count === 1) return "استشارة واحدة";
  if (count === 2) return "استشارتين";
  if (count >= 3 && count <= 10) return `${count} استشارات`;
  return `${count} استشارة`;
}

export const dashboard: DashboardMessages = {
  oneMoment: "لحظة واحدة…",
  toDashboard: "جارٍ نقلكِ إلى لوحة التحكم…",
  subtitleActive: "لديكِ محادثة قيد التقدّم. تابعي من حيث توقفتِ، أو ابدئي من جديد.",
  subtitleCompleted: (count: number) =>
    `أكملتِ ${consultations(count)}. يمكنكِ بدء محادثة جديدة في أي وقت.`,
  subtitleSaved: "محادثاتكِ محفوظة هنا. افتحي إحداها أو ابدئي محادثة جديدة.",
  subtitleNew: "أخبرينا بما تشعرين به، وسنطرح بعض الأسئلة ونساعدكِ على تحديد الخطوة التالية.",
  yourHome: "صفحتكِ الرئيسية",
  greeting: (name: string) => `مرحبًا، ${name}`,
  greetingAnonymous: "مرحبًا",
  accountSettings: "إعدادات الحساب",
  tryAgain: "حاولي مرة أخرى",
  chatTitle: "المحادثة الصحية",
  ready: "جاهزة",
  chatContinue: "تابعي محادثة أو ابدئي واحدة جديدة",
  chatMain: "طريقتكِ الأساسية لاستخدام HerHealthGPT",
  chatPitch:
    "هل يشغل بالكِ شيء؟ صفيه بكلماتكِ. سنطرح بعض أسئلة المتابعة عند الحاجة، ثم نقترح متى يجب أن تُراجَعي، مع روابط إلى مصادر موثوقة. هذا ليس تشخيصًا.",
  openChat: "فتح المحادثة الصحية",
  startChat: "ابدئي محادثة",
  continueChat: "تابعي محادثتكِ",
  takesMinutes: "تستغرق عادةً بضع دقائق.",
  scaleTitle: "الإجابات الأربع التي قد تنتهي بها المحادثة",
  scaleLead:
    "لا نخبركِ أبدًا بما لديكِ. تنتهي كل استشارة بوضع ما وصفتِه على هذا المقياس، مع المصادر التي يستند إليها.",
  topicsTitle: "موضوعات تصفّحتِها",
  topicsLead: "أنماط تربطها مصادرنا بأعراض تحدّثتِ عنها، وليست تشخيصًا.",
  comingLater: "قريبًا",
  healthLog: "السجل الصحي",
  healthLogBody: "تتبّعي دورتكِ وأعراضكِ مع الوقت، ونعمل على هذه الميزة الآن.",
  allSet: "كل شيء جاهز",
  allSetBody:
    "حُفظت محادثتكِ الصحية الأولى. ستعرض لوحة التحكم هذه المحادثات الأخيرة وقراءات من مصادر موثوقة مع الوقت.",
  gotIt: "فهمت",
  oneStepLeft: "خطوة واحدة متبقية",
  oneStepLeftBody: "ابدئي محادثة صحية حين تكونين مستعدة. سنطرح بعض الأسئلة ونساعدكِ على تحديد الخطوة التالية.",
  startFirstChat: "ابدئي محادثتكِ الأولى",
  recentChats: "المحادثات الأخيرة",
  viewAll: "عرض الكل",
  done: "منتهية",
  inProgress: "قيد التقدّم",
  recommended: "مقترحة لكِ",
  explore: "استكشفي موضوعات موثوقة",
  recommendedLead: "مقالات من المصادر التي نستشهد بها في محادثاتكِ، وقراءات ذات صلة.",
  exploreLead: "مختارة من MedlinePlus وNICHD ومكتب صحة المرأة.",
  articlesDisclaimer:
    "معلومات فقط، وليست نصيحة طبية. لا نشخّص أبدًا. راجعي مختصًا إن كنتِ قلقة.",
  fromYourChat: "من محادثتكِ",
  readOn: (source: string) => `اقرئي على ${source}`,
  articlesInEnglish: "تُفتح المقالات على موقع المصدر نفسه، باللغة الإنجليزية.",
};

export const conditions: Record<string, string> = {
  pcos: "متلازمة تكيّس المبايض",
  endometriosis: "الانتباذ البطاني الرحمي (بطانة الرحم المهاجرة)",
  uterine_fibroids: "الأورام الليفية في الرحم",
  normal_variation: "تغيّر طبيعي",
  pelvic_inflammatory_disease: "مرض التهاب الحوض",
  perimenopause: "مرحلة ما حول انقطاع الطمث",
  ovarian_cyst: "أكياس المبيض",
  urinary_tract_infection: "التهاب المسالك البولية",
  sexually_transmitted_infection: "العدوى المنقولة جنسيًا",
  thrush: "عدوى الخميرة المهبلية",
  bacterial_vaginosis: "التهاب المهبل البكتيري",
  adenomyosis: "العُضال الغدّي",
  hypothyroidism: "أمراض الغدة الدرقية",
  primary_ovarian_insufficiency: "انقطاع الطمث المبكر",
  inherited_bleeding_disorder: "اضطرابات النزيف",
  bladder_pain: "ألم المثانة",
  pelvic_organ_prolapse: "هبوط أعضاء الحوض",
  iron_deficiency_anaemia: "نقص الحديد",
  infertility: "صعوبة الإنجاب",
};

/** Curated article titles and summaries; the pages themselves are in English. */
export const articles: ArticleMessages = {
  items: {
  menstruation: { title: "دورتكِ الشهرية", excerpt: "كيف تبدو الدورة الطبيعية، والتغيّرات الشائعة، ومتى يجب مراجعة طبيب." },
  endometriosis: { title: "الانتباذ البطاني الرحمي (بطانة الرحم المهاجرة)", excerpt: "الأعراض والأسباب، ومتى يحتاج ألم الحوض أثناء الدورة إلى فحص أدق." },
  pcos: { title: "متلازمة تكيّس المبايض", excerpt: "عدم انتظام الدورة، والتغيّرات الهرمونية، وما تقوله المصادر عن هذه المتلازمة." },
  fibroids: { title: "الأورام الليفية في الرحم", excerpt: "النزيف الغزير، والضغط في الحوض، ومتى قد يستحق الأمر النقاش مع مختص." },
  uti: { title: "التهابات المسالك البولية", excerpt: "الحرقة والإلحاح، ومتى تحتاج أعراض المسالك البولية إلى علاج." },
  infertility: { title: "صعوبة الإنجاب", excerpt: "محاولة الإنجاب، والأسباب الشائعة، ومتى يجب التحدث إلى مختص." },
  thyroid: { title: "أمراض الغدة الدرقية", excerpt: "كيف تؤثر مشاكل الغدة الدرقية في الدورة والطاقة والوزن." },
  sti: { title: "العدوى المنقولة جنسيًا", excerpt: "الأعراض والفحوص، ولماذا قد تحتاج الإفرازات أو ألم الحوض إلى فحص." },
} as Record<string, { title: string; excerpt: string }>,
  relatedTo: (label: string) => `مرتبط بـ${label} من محادثتكِ`,
  citedRecently: "ورد في محادثتكِ الأخيرة",
  basedOnTopics: "بناءً على موضوعات من محادثاتكِ",
  fromRecentChat: "من محادثتكِ الأخيرة",
};

/** Source names that read differently in this language; the rest are brand names. */
export const sourceNames: Record<string, string> = {
  womenshealth: "مكتب صحة المرأة (الولايات المتحدة)",
};
