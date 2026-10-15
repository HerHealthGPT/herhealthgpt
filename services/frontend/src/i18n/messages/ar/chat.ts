import type { ChatMessages } from "../en/chat";

function sources(count: number): string {
  if (count === 1) return "مصدر واحد آخر";
  if (count === 2) return "مصدران آخران";
  if (count >= 3 && count <= 10) return `${count} مصادر أخرى`;
  return `${count} مصدرًا آخر`;
}

export const chat: ChatMessages = {
  greeting: (name: string | null) =>
    `${name ? `مرحبًا ${name}` : "مرحبًا"}، أنا هنا لمساعدتكِ على معرفة الخطوة التالية. أخبريني بما يحدث معكِ بكلماتكِ، وسأطرح بعض أسئلة المتابعة إن احتجت.`,
  firstQuestionWait: "السؤال الأول، يستغرق عادةً من 15 إلى 60 ثانية",
  followUpWait: (turn: number) => `المتابعة رقم ${turn}، ما زلنا نراجع المصادر`,
  couldNotOpen: "لم نتمكن من فتح هذه المحادثة. ابدئي محادثة جديدة أدناه، فما زلنا هنا للمساعدة.",
  chatDeleted: "تم حذف المحادثة",
  loadingConversation: "جارٍ تحميل المحادثة…",
  tryAgain: "حاولي مرة أخرى",
  complete: "اكتملت هذه المحادثة. ابدئي محادثة جديدة إن ظهر أمر آخر.",
  startNewChat: "ابدئي محادثة جديدة",
  placeholderFirst: "أخبريني بما يحدث معكِ…",
  placeholderReply: "اكتبي ردّكِ…",
  footer: "قد يخطئ HerHealthGPT. يقدّم إرشادًا حول مدى الاستعجال، وليس تشخيصًا.",
  composerLabel: "اكتبي ما يحدث معكِ",
  send: "إرسال",
  sendLabel: "إرسال الرسالة",
  waitHint: "قد يستغرق الرد الأول حتى دقيقة، وسنعرض التقدّم أثناء الانتظار.",
  tapSend: "اضغطي إرسال حين تكونين مستعدة.",
  keyboardHint: "Enter للإرسال · Shift+Enter لسطر جديد",
  concludedBanner: "اكتملت هذه الاستشارة. ابدئي محادثة جديدة إن ظهر أمر آخر.",
  newChat: "محادثة جديدة",
  openSidebar: "فتح الشريط الجانبي",
  closeSidebar: "إغلاق الشريط الجانبي",
  dashboardShort: "لوحة التحكم",
  backToDashboard: "العودة إلى لوحة التحكم",
  starterIntro: "لا تعرفين من أين تبدئين؟ جرّبي إحدى هذه:",
  starters: [
    "دورتي الشهرية غير منتظمة مؤخرًا",
    "النزيف عندي أغزر من المعتاد",
    "أحاول الإنجاب منذ فترة",
    "عندي ألم في الحوض لا يزول",
  ],
  basedOn: "استنادًا إلى",
  sources: "المصادر",
  lookedUpLive: "بحث مباشر",
  warningSign: "علامة تحذيرية",
  moreSources: (count: number) => `و${sources(count)}`,
  patterns: "أنماط محتملة من مصادرنا (ليست تشخيصًا)",
  redFlagNote:
    "هذا نمط من الأعراض يفحصه الأطباء سريعًا، لأن له أسبابًا محتملة عدة، وبعضها يجب استبعاده بسرعة.",
  disclaimerTitle: "تنبيه",
  disclaimer:
    "هذا إرشاد حول مدى الاستعجال مستند إلى مصادر مذكورة، وليس تشخيصًا. نحن أداة ذكاء اصطناعي ولسنا مختصين، وقد نخطئ، فإن شعرتِ بأي شك، يُرجى مراجعة طبيب.",
  declineNote: "لا يظهر هنا مستوى استعجال ولا مصادر، لأنه لم يُقيَّم شيء.",
  showReasoning: "إظهار التعليل",
  hideReasoning: "إخفاء التعليل",
  thinking: [
    "نقرأ ما شاركتِه…",
    "نبحث في مصادر صحية موثوقة…",
    "نفكّر في السؤال التالي…",
    "ما زلنا نعمل، فبعض الحالات تستغرق دقيقة…",
    "اقتربنا، شكرًا على انتظاركِ…",
  ],
  version: "النسخة",
  versionLocked: "ابدئي محادثة جديدة لتجربة نسخة أخرى",
  compareBanner:
    "أنتِ تساعديننا في مقارنة نسخ مختلفة. بعض الإجابات لا يُتحقَّق منها مقابل مصادرنا. هذه معلومات وليست نصيحة طبية.",
  unreviewed: (label: string) =>
    `${label}: للمقارنة فقط. هذا النموذج غير مراجَع لقرارات الفرز، ويميل إلى الاستنتاج قبل طرح أسئلة كافية. لا تعتمدي على هذه الإجابة.`,
  groups: {
    today: "اليوم",
    yesterday: "أمس",
    week: "آخر 7 أيام",
    older: "أقدم",
  },
  closeAccountMenu: "إغلاق قائمة الحساب",
  accountMenu: "قائمة الحساب",
  yourAccount: "حسابكِ",
  manageProfile: "إدارة الملف الشخصي",
  completed: "مكتملة",
  deleteConfirm: "حذف هذه المحادثة نهائيًا؟",
  cancel: "إلغاء",
  delete: "حذف",
  deleteChat: "حذف المحادثة",
  deleteChatLabel: (preview: string) => `حذف المحادثة: ${preview}`,
};
