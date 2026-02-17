import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Cloud Classroom Provisioning',
  tagline: 'Infrastructure as Code for Cloud Classroom Environments',
  favicon: 'img/favicon.ico',

  // Set the production url of your site here
  url: 'https://Bassaganas.github.io',
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: '/cloud-classroom-provisioning/',

  // GitHub pages deployment config.
  organizationName: 'Bassaganas',
  projectName: 'cloud-classroom-provisioning',

  onBrokenLinks: 'throw',
  onBrokenMarkdownLinks: 'warn',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/Bassaganas/cloud-classroom-provisioning/tree/main/website/',
          showLastUpdateAuthor: true,
          showLastUpdateTime: true,
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/docusaurus-social-card.jpg',
    navbar: {
      title: 'Cloud Classroom',
      logo: {
        alt: 'Cloud Classroom Logo',
        src: 'img/logo.svg',
        width: 32,
        height: 32,
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Documentation',
        },
        {
          href: 'https://github.com/Bassaganas/cloud-classroom-provisioning',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'Getting Started',
              to: '/docs/getting-started/quick-start',
            },
            {
              label: 'Architecture',
              to: '/docs/architecture/overview',
            },
            {
              label: 'Deployment',
              to: '/docs/deployment/guide',
            },
          ],
        },
        {
          title: 'Resources',
          items: [
            {
              label: 'API Reference',
              to: '/docs/usage/api',
            },
            {
              label: 'Troubleshooting',
              to: '/docs/reference/troubleshooting',
            },
            {
              label: 'Contributing',
              to: '/docs/contributing',
            },
          ],
        },
        {
          title: 'More',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/Bassaganas/cloud-classroom-provisioning',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Cloud Classroom Provisioning. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'json', 'yaml', 'hcl'],
    },
    colorMode: {
      defaultMode: 'light',
      disableSwitch: false,
      respectPrefersColorScheme: true,
    },
  },
  markdown: {
    mermaid: true,
  },
  themes: ['@docusaurus/theme-mermaid'],
} satisfies Config;

export default config;
