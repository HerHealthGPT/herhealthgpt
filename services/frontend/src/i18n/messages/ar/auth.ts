import type { AuthMessages, CommonMessages, ErrorMessages, NavMessages } from "../en/auth";

export const common: CommonMessages = {
  appName: "HerHealthGPT",
  metaDescription:
    "محادثة صحية للنساء. تحدّثي عن أعراضكِ، واعرفي ما قد تتوافق معه من حالات، وما الخطوة التالية. لسنا طبيبًا.",
  loading: "جارٍ التحميل…",
  email: "البريد الإلكتروني",
  emailPlaceholder: "you@example.com",
  password: "كلمة المرور",
  showPassword: "إظهار كلمة المرور",
  hidePassword: "إخفاء كلمة المرور",
  signIn: "تسجيل الدخول",
  signUp: "إنشاء حساب",
  signOut: "تسجيل الخروج",
  openMenu: "فتح القائمة",
  closeMenu: "إغلاق القائمة",
  language: "اللغة",
  sending: "جارٍ الإرسال…",
  resendCode: "إعادة إرسال الرمز",
  passwordHint: "8 أحرف على الأقل.",
  passwordsDoNotMatch: "كلمتا المرور غير متطابقتين.",
  codePlaceholder: "000000",
};

export const nav: NavMessages = {
  healthChat: "المحادثة الصحية",
  dashboard: "لوحة التحكم",
  account: "الحساب",
  howItWorks: "كيف يعمل",
};

export const auth: AuthMessages = {
  shell: {
    heading: "لستِ متأكدة إن كان عليكِ مراجعة أحد؟",
    pitch:
      "صفي ما يحدث معكِ بكلماتكِ. سنطرح عليكِ بعض الأسئلة، ثم نخبركِ متى يجب أن تُراجَعي، ونريكِ من أين جاءت هذه المعلومة.",
    smallPrint:
      "إرشاد حول مدى الاستعجال ومعلومات صحية، وليس تشخيصًا أبدًا. اسألي بالعربية أو الإنجليزية أو الفرنسية.",
  },
  signIn: {
    title: "مرحبًا بعودتكِ",
    description: "سجّلي الدخول لفتح محادثتكِ الصحية.",
    noAccount: "ليس لديكِ حساب؟",
    createOne: "أنشئي حسابًا",
    forgotPassword: "نسيتِ كلمة المرور؟",
    submitting: "جارٍ تسجيل الدخول…",
    submit: "تسجيل الدخول بالبريد الإلكتروني",
  },
  signUp: {
    title: "أنشئي حسابكِ",
    descriptionWithGoogle: "تابعي باستخدام Google، أو أنشئي حسابًا ببريدكِ الإلكتروني.",
    description: "الاستخدام مجاني. سنرسل رمزًا سريعًا لتأكيد بريدكِ الإلكتروني.",
    haveAccount: "لديكِ حساب بالفعل؟",
    divider: "أو أنشئي حسابًا بالبريد الإلكتروني",
    confirmPassword: "تأكيد كلمة المرور",
    submitting: "جارٍ إنشاء الحساب…",
    submit: "إنشاء حساب بالبريد الإلكتروني",
    disclaimer:
      "يقدّم هذا التطبيق معلومات صحية. وهو ليس تشخيصًا ولسنا طبيبًا. راجعي طبيبًا إن كنتِ قلقة.",
  },
  verify: {
    title: "تأكيد بريدكِ الإلكتروني",
    description: "أرسلنا رمزًا من 6 أرقام إلى بريدكِ الإلكتروني. أدخليه أدناه.",
    alreadyVerified: "هل أكّدتِ بريدكِ من قبل؟",
    code: "رمز التأكيد",
    codeHint:
      "تحقّقي من صندوق الوارد ومجلد الرسائل غير المرغوب فيها. تنتهي صلاحية الرموز بعد وقت قصير، فاضغطي على إعادة الإرسال أدناه إن انتهت صلاحية رمزكِ.",
    submitting: "جارٍ التأكيد…",
    submit: "تأكيد البريد الإلكتروني",
    verified: "تم تأكيد البريد الإلكتروني. أهلًا بكِ!",
    resent: "إذا كان هذا العنوان مسجّلًا، فقد أُرسل رمز جديد.",
  },
  forgot: {
    title: "إعادة تعيين كلمة المرور",
    descriptionSent:
      "ابحثي في بريدكِ عن رمز إعادة التعيين المكوّن من 6 أرقام، ثم تابعي لتعيين كلمة مرور جديدة.",
    description: "أدخلي بريدكِ الإلكتروني وسنرسل إليكِ رمز إعادة التعيين إن كان هناك حساب.",
    remember: "تذكّرتِ كلمة المرور؟",
    privacyNote:
      "لن نخبركِ إن كان البريد الإلكتروني مسجّلًا. إذا وصلكِ رمز، فاستخدمي الزر أدناه لإدخاله.",
    enterCode: "إدخال رمز إعادة التعيين",
    submit: "إرسال رمز إعادة التعيين",
    sent: "إذا كان هذا العنوان مسجّلًا، فقد أُرسل رمز إعادة التعيين.",
  },
  reset: {
    title: "تعيين كلمة مرور جديدة",
    description: "أدخلي الرمز الوارد في بريدكِ واختاري كلمة مرور جديدة.",
    needCode: "تحتاجين إلى رمز جديد؟",
    requestAnother: "اطلبي رمزًا آخر",
    code: "رمز إعادة التعيين",
    newPassword: "كلمة المرور الجديدة",
    confirmNewPassword: "تأكيد كلمة المرور الجديدة",
    submitting: "جارٍ التحديث…",
    submit: "تحديث كلمة المرور",
    updated: "تم تحديث كلمة المرور. يُرجى تسجيل الدخول بكلمة المرور الجديدة.",
  },
  google: {
    noCredential: "لم يُرجع تسجيل الدخول عبر Google بيانات اعتماد.",
    cancelled: "أُلغي تسجيل الدخول عبر Google أو فشل.",
    signingIn: "جارٍ تسجيل دخولكِ…",
    divider: "أو استخدمي البريد الإلكتروني",
  },
  errors: {
    passwordRequirements: "لم تُستوفَ شروط كلمة المرور:",
  },
  guard: {
    loadingAccount: "جارٍ تحميل حسابكِ…",
    almostThere: "اقتربنا…",
    oneThingFirst: "أمر واحد أولًا…",
  },
};

export const errors: ErrorMessages = {
  generic: "حدث خطأ ما. يُرجى المحاولة مرة أخرى.",
  network: "تعذّر الوصول إلى الخادم. تحقّقي من اتصالكِ وحاولي مرة أخرى.",
  sessionEnded: "انتهت جلستكِ. يُرجى تسجيل الدخول مرة أخرى للمتابعة.",
  unavailable: "الخدمة غير متاحة مؤقتًا. حاولي بعد قليل.",
  chatUnavailable: "المحادثة غير متاحة الآن. يُرجى المحاولة بعد قليل.",
  wrongTurn: "حدث خطأ من جهتنا. يُرجى المحاولة مرة أخرى.",
  tooSlow: "يستغرق هذا وقتًا أطول من المعتاد. يُرجى المحاولة مرة أخرى.",
  conversationGone: "هذه المحادثة لم تعد متاحة. ابدئي محادثة جديدة للمتابعة.",
  addWords: "جرّبي إضافة بضع كلمات عمّا يحدث معكِ.",
  deleteFailed: "تعذّر حذف المحادثة، فقد يحتاج الخادم إلى إعادة تشغيل لتطبيق آخر تحديث.",
  passwordTooShort: "يجب أن تتكوّن من 8 أحرف على الأقل",
  passwordTooLong: "أطول من الحد المسموح",
  passwordCommon: "شائعة جدًا ولا يمكن استخدامها ككلمة مرور",
  /** The account API's fixed English sentences, by their exact text. */
  server: {
    "This email address is already registered.": "هذا البريد الإلكتروني مسجّل بالفعل.",
    "Incorrect email address or password.": "البريد الإلكتروني أو كلمة المرور غير صحيحة.",
    "Too many attempts. Try again later.": "محاولات كثيرة جدًا. حاولي لاحقًا.",
    "Not signed in.": "لم تسجّلي الدخول.",
    "That code is incorrect.": "هذا الرمز غير صحيح.",
    "This code has expired. Request a new one.": "انتهت صلاحية هذا الرمز. اطلبي رمزًا جديدًا.",
    "Your Google sign-in could not be verified.": "تعذّر التحقق من تسجيل دخولكِ عبر Google.",
    "Signing in with Google is not available yet.": "تسجيل الدخول عبر Google غير متاح بعد.",
    "This account signs in with Google. There is no password to reset.": "يسجّل هذا الحساب الدخول عبر Google، فلا توجد كلمة مرور لإعادة تعيينها.",
    "Name must be between 1 and 80 characters.": "يجب أن يكون الاسم بين حرف واحد و80 حرفًا.",
  } as Record<string, string>,
};
