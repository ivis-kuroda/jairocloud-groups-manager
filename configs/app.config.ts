// Application configuration for client side
/* eslint-disable @stylistic/max-len */

/**
 * Server hostname of this application \
 * [Mandatory]
 */
const serverName = 'localhost' as string

/**
 * Base URL of this application \
 * [Mandatory]
 */
const baseURL = `https://${serverName}` as string

const header = {
  /**
   * Path to the logo image file \
   * Example: "/logo.png" \
   * [Mandatory]
   */
  serviceLogo: '/logo.png' as string,

  /**
   * Alt name for the logo image file \
   * [Mandatory]
   */
  serviceAltName: 'JAIRO Cloud Groups Manager' as string,

  /**
   * URL or path to the user manual page \
   * If set to an empty string, the link to the user manual will not be displayed. \
   * [Optional, can be left empty]
   */
  userManualURL: '' as string,

  /**
   * Configuration for global search in the header
   */
  globalSearch: {
    /**
     * Maximum number of search results to be returned for each category in the global search. \
     * [Mandatory]
     */
    limit: 5,
  },
}

const footer = {
  /** Configuration for links in the footer */
  links: {
    /**
     * URL or path to the privacy policy page. \
     * [Optional, can be left empty]
     */
    'privacy-policy': '' as string,
    /**
     * URL or path to the terms of service page. \
     * [Optional, can be left empty]
     */
    'terms-of-service': '' as string,
  },
}

const table = {
  /**
   * Options for page size selection in tables
   */
  pageSize: {
    repositories: [20, 50, 100] as [number, ...number[]],
    groups: [20, 50, 100] as [number, ...number[]],
    users: [20, 50, 100] as [number, ...number[]],
    history: [20, 50, 100] as [number, ...number[]],
    bulks: [20, 50, 100] as [number, ...number[]],
    cacheGroups: [20, 50, 100] as number[],
  },
}

const repositories = {
  /**
   * Maximum length of the URL ID entered in the repository creation form \
   * (excluding “https://”, the “jc_” prefix assigned to the ID, and additional padding) \
   * If you change this setting, you must also change setting `repositories.max_url_length`
   * in `server.config.toml` accordingly to keep them consistent.
   * [Mandatory]
   */
  maxUrlLength: 50 - 'jc_'.length - '_ro_radm'.length - 2,
}

const groups = {
  /**
   * Maximum length of the URL ID entered in the group creation form \
   * (excluding the “jc_” prefix assigned to the ID and additional padding) \
   * [Mandatory]
   */
  maxIdLength: 50 - 'jc_'.length - '_gr_'.length,
}

const polling = {
  /**
   * Interval time (in milliseconds) for polling requests to check the status of task\
   */
  interval: 2000,

  /**
   * Maximum number of attempts for polling requests to check the status of task\
   */
  maxAttempts: 100,
}

const wayf = {
  /**
   * URL of the WAYF to use \
   * Examples: "https://wayf.switch.ch/SWITCHaai/WAYF", "https://wayf-test.switch.ch/aaitest/WAYF"; \
   * [Mandatory]
   */
  URL: 'https://test-ds.gakunin.nii.ac.jp/WAYF' as string,

  /**
   * URL of the JavaScript file to write embedded WAYF \
   * [Mandatory]
   */
  jsURL: 'https://test-ds.gakunin.nii.ac.jp/WAYF/embedded-wayf.js' as string,

  /**
   * EntityID of the Service Provider that protects this Resource Server \
   * Examples: "https://econf.switch.ch/shibboleth", "https://dokeos.unige.ch/shibboleth" \
   * [Mandatory]
   */
  spEntityID: `${baseURL}/shibboleth-sp` as string,

  /**
   * Shibboleth Service Provider handler URL \
   * Examples: "https://point.switch.ch/Shibboleth.sso", "https://rr.aai.switch.ch/aaitest/Shibboleth.sso" \
   * [Mandatory, if wayf_use_discovery_service = false]
   */
  spHandlerURL: `${baseURL}/Shibboleth.sso` as string,

  /**
   * URL on this resource that the user shall be returned to after authentication \
   * Examples: "https://econf.switch.ch/aai/home", "https://olat.uzh.ch/my/courses" \
   * [Mandatory]
   */
  returnURL: `${baseURL}/secure` as string,

  /**
   * Most used Identity Providers will be shown as top category in the drop down \
   * list if this feature is used. \
   * [Optional, commented out by default] \
   * var wayf_most_used_idps =  new Array("https://aai-logon.unibas.ch/idp/shibboleth", "https://aai.unil.ch/idp/shibboleth");
   */
  mostUsedIdps: [
  ] as string[],

  /**
   * Categories of Identity Provider that shall not be shown \
   * Possible values are: "hokkaido","tohoku","kanto","chubu","kinki","chugoku","shikoku","kyushu","others", "all" \
   * Example of how to hide categories \
   * var wayf_hide_categories =  new Array("other", "library"); \
   * [Optional, commented out by default]
   */
  hideCategories: ['all'] as string[],

  /**
   * EntityIDs of Identity Provider whose category is hidden but that shall be shown anyway \
   * If this array is not empty, wayf_show_categories will be disabled because \
   * otherwise, unhidden IdPs may be displayed in the wrong category \
   * Example of how to unhide certain Identity Providers \
   * var wayf_unhide_idps = new Array("https://aai-login.uzh.ch/idp/shibboleth"); \
   * [Optional, commented out by default]
   */
  unhideIdps: [
    'https://jctest.exticgakunin.com/auth/gakunin/saml2/assertions',
    'https://core-stg.orthros.gakunin.nii.ac.jp/idp',
  ] as string[],

  /**
   * EntityIDs of Identity Provider that shall not be shown at all \
   * Example of how to hide certain Identity Provider \
   * var wayf_hide_idps = new Array("https://idp.unige.ch/idp/shibboleth", "https://lewotolo.switch.ch/idp/shibboleth"); \
   * [Optional, commented out by default]
   */
  hideIdps: [
  ] as string[],

  /**
   * EntityIDs, Names and SSO URLs of Identity Providers from other federations \
   * that shall be added to the drop-down list \
   * The IdPs will be displayed in the sequence they are defined \
   * [Optional, commented out by default]
   */
  additionalIdPs: [
    { name: 'Orthros-Test', entityID: 'https://core-stg.orthros.gakunin.nii.ac.jp/idp' },
  ] as { name: string, entityID: string }[],
}

/**
 * These are due to temporary constraints
 * in the future, all features will be enabled and the settings will be deleted.
 */
const features = {
  /** repositories feature flags */
  repositories: {
    /**
     * If true, the search will be performed on the server side.
     * If false, the search will be performed on the client (browser) side.
     */
    'server-search': false,

    /** Whether to allow sorting columns */
    'sort-columns': false,
  },
  /** groups feature flags */
  groups: {
    /** Whether to allow sorting columns */
    'sort-columns': false,
  },
  /** users feature flags */
  users: {
    /** Whether to allow filters to be applied at the same time for both roles and groups */
    'filter-by-both-role-group': false,
    /** Whether to allow the last modified filter */
    'filter-by-last-modified': false,
    /** Whether to allow the search by username only */
    'search-only-username': true,
    /** Whether to allow sorting columns */
    'sort-columns': false,
    /** Whether to display file upload button */
    'file-upload': false,
  },
  /** history feature flags */
  history: {
    /** Whether to display history upload tab */
    upload: false,
  },
}

export default {
  /** Server hostname of this application */
  serverName,
  /** Base URL of this application */
  baseURL,
  /** Header configuration */
  header,
  /** Footer configuration */
  footer,
  /** Table configuration */
  table,
  /** Repository configuration */
  repositories,
  /** Group configuration */
  groups,
  /** Polling configuration */
  polling,
  /** WAYF (Embedded DS) configuration */
  wayf,
  /**
   * Feature flags configuration. \
   * These are due to temporary constraints
   * in the future, all features will be enabled and the settings will be deleted.
   */
  features,
}
