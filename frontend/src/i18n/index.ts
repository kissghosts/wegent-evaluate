'use client'

import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import enCommon from './locales/en/common.json'
import zhCommon from './locales/zh-CN/common.json'

const resources = {
  en: {
    common: enCommon,
  },
  'zh-CN': {
    common: zhCommon,
  },
}

/**
 * Important: keep the initial language deterministic between SSR and hydration.
 *
 * LanguageProvider (client-side) will switch language after mount based on
 * localStorage / browser language.
 */
i18n.use(initReactI18next).init({
  resources,
  lng: 'en',
  fallbackLng: 'en',
  defaultNS: 'common',
  interpolation: {
    escapeValue: false,
  },
})

export default i18n
