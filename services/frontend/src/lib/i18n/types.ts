export type Language = 'en' | 'ko';

export interface Translations {
  // Navigation
  nav: {
    dashboard: string;
    upload: string;
    search: string;
  };

  // Common
  common: {
    loading: string;
    error: string;
    save: string;
    cancel: string;
    delete: string;
    edit: string;
    search: string;
    upload: string;
    download: string;
    submit: string;
    back: string;
    next: string;
    signIn: string;
    signUp: string;
    signOut: string;
    email: string;
    password: string;
    name: string;
    description: string;
  };

  // Landing page
  landing: {
    title: string;
    subtitle: string;
    getDemo: string;
    heroTitle1: string;
    heroTitle2: string;
    heroDescription: string;
    requestDemo: string;
    getStarted: string;
    featuresTitle: string;
    featuresSubtitle: string;
    feature1Title: string;
    feature1Description: string;
    feature2Title: string;
    feature2Description: string;
    feature3Title: string;
    feature3Description: string;
    howItWorksTitle: string;
    howItWorksSubtitle: string;
    step1Title: string;
    step1Description: string;
    step2Title: string;
    step2Description: string;
    step3Title: string;
    step3Description: string;
    ctaTitle: string;
    ctaDescription: string;
    scheduleDemo: string;
    contactSales: string;
    footerTagline: string;
    footerCopyright: string;
  };

  // Auth
  auth: {
    appTitle: string;
    appSubtitle: string;
    signInTitle: string;
    signUpTitle: string;
    emailPlaceholder: string;
    passwordPlaceholder: string;
    signInButton: string;
    signUpButton: string;
    toggleSignUp: string;
    toggleSignIn: string;
    signingIn: string;
    signingUp: string;
    signupSuccessTitle: string;
    signupSuccessMessage: string;
  };

  // Onboarding
  onboarding: {
    title: string;
    subtitle: string;
    fullName: string;
    fullNameRequired: string;
    industry: string;
    industryPlaceholder: string;
    jobTitle: string;
    jobTitlePlaceholder: string;
    preferredLanguage: string;
    preferredLanguageRequired: string;
    preferredLanguageHelp: string;
    marketingConsent: string;
    continueButton: string;
    saving: string;
    completeSetup: string;
  };

  // Dashboard
  dashboard: {
    title: string;
    welcome: string;
    uploadVideo: string;
    searchVideos: string;
    noVideos: string;
    uploadFirst: string;
    yourVideos: string;
    viewDetails: string;
    startProcessing: string;
    duration: string;
    resolution: string;
    uploaded: string;
    error: string;
    status: {
      PENDING: string;
      PROCESSING: string;
      READY: string;
      FAILED: string;
    };
    totalVideos: string;
    ready: string;
    processing: string;
    pending: string;
    videos: string;
    uploadFirstVideo: string;
    processingStarted: string;
    failedToProcess: string;
  };

  // Upload
  upload: {
    title: string;
    dragDrop: string;
    orBrowse: string;
    selectedFile: string;
    uploadButton: string;
    uploading: string;
    uploadSuccess: string;
    uploadError: string;
    backToDashboard: string;
    sceneDetectionMethod: string;
    sceneDetectionHelp: string;
    methods: {
      content: string;
      threshold: string;
      adaptive: string;
    };
  };

  // Search
  search: {
    title: string;
    searchPlaceholder: string;
    searchButton: string;
    searching: string;
    noResults: string;
    resultsFound: string;
    scene: string;
    timestamp: string;
    viewVideo: string;
    subtitle: string;
    results: string;
    enterQuery: string;
    enterQueryDescription: string;
    tryAdjusting: string;
    allFilesHidden: string;
    enableFiles: string;
    match: string;
    videoPlayer: string;
    selectScene: string;
    visualDescription: string;
    transcript: string;
    detectedEntities: string;
    detectedActions: string;
    tags: string;
  };

  // Video Details
  videoDetails: {
    title: string;
    loading: string;
    notFound: string;
    backToDashboard: string;
    videoInfo: string;
    fileName: string;
    uploadedAt: string;
    status: string;
    scenes: string;
    transcript: string;
    visualSummary: string;
    visualDescription: string;
    detectedEntities: string;
    detectedActions: string;
    tags: string;
    metadata: string;
    sceneNumber: string;
    timeRange: string;
    noScenes: string;
    noTranscript: string;
    noVisualSummary: string;
    noMetadata: string;
    processingDetails: string;
    aiAnalyzed: string;
    goToDashboard: string;
    details: string;
    transcriptView: string;
    frameRate: string;
    recordingInfo: string;
    location: string;
    camera: string;
    recorded: string;
    settings: string;
    videoSummary: string;
    collapse: string;
    expand: string;
    allTags: string;
    clearFilter: string;
    sceneBreakdown: string;
    filtered: string;
    transcriptSegments: string;
    noTranscriptShort: string;
    exportToShort: string;
    tooLong: string;
    selectSegment: string;
    visual: string;
    processingInProgress: string;
    noScenesWithTag: string;
  };

  // Reprocess
  reprocess: {
    button: string;
    title: string;
    description: string;
    languageLabel: string;
    languageHelp: string;
    autoDetect: string;
    languages: {
      ko: string;
      en: string;
      ja: string;
      zh: string;
      es: string;
      fr: string;
      de: string;
      ru: string;
      pt: string;
      it: string;
    };
    cancel: string;
    confirm: string;
    processing: string;
    success: string;
    started: string;
    completed: string;
    failed: string;
    error: string;
  };

  // Search Weights
  searchWeights: {
    title: string;
    loadingPreferences: string;
    usingSavedDefaults: string;
    custom: string;
    presets: string;
    balanced: string;
    visual: string;
    dialogue: string;
    keywords: string;
    useSavedDefaults: string;
    reset: string;
    saveAsDefault: string;
    savedAsDefault: string;
    failedToSave: string;
    appliedPreset: string;
    usingSaved: string;
    usingSystem: string;
    customActive: string;
    resetToSaved: string;
    resetToSystem: string;
    modifyHint: string;
  };

  // File Filter
  fileFilter: {
    title: string;
    showing: string;
    files: string;
    scenes: string;
    all: string;
    none: string;
    clickToHide: string;
    clickToShow: string;
  };

  // Export
  export: {
    title: string;
    sceneDuration: string;
    exceedsMax: string;
    aspectRatioStrategy: string;
    centerCrop: string;
    cropTo916: string;
    letterbox: string;
    addBlackBars: string;
    quality: string;
    highQuality: string;
    mediumQuality: string;
    status: string;
    queued: string;
    processing: string;
    ready: string;
    failed: string;
    waitingForWorker: string;
    convertingVideo: string;
    usuallyTakes: string;
    downloadVideo: string;
    size: string;
    resolution: string;
    expires: string;
    exportFailed: string;
    unknownError: string;
    limitReached: string;
    cancel: string;
    starting: string;
    exportButton: string;
    close: string;
  };
}
