import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  emoji: string;
  description: JSX.Element;
};

const FeatureList: FeatureItem[] = [
  {
    title: 'Quick Deployment',
    emoji: '🚀',
    description: (
      <>
        Deploy complete cloud classroom infrastructure with a single command.
        Supports AWS and Azure with automated setup.
      </>
    ),
  },
  {
    title: 'Student Management',
    emoji: '👥',
    description: (
      <>
        Automatically create and manage student accounts with appropriate
        permissions. Pre-configured EC2 instances with Dify AI and Jenkins.
      </>
    ),
  },
  {
    title: 'Cost Control',
    emoji: '💰',
    description: (
      <>
        Automatically stop and terminate idle instances to minimize cloud costs.
        Web-based UI for instructors to manage everything.
      </>
    ),
  },
];

function Feature({title, emoji, description}: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <div className={styles.featureEmoji}>{emoji}</div>
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): JSX.Element {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
