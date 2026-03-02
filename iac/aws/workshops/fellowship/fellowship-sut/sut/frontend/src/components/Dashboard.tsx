import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Quest, Member } from '../types';
import { Card } from './ui/Card';
import { Alert } from './ui/Alert';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import { CharacterPanel } from './characters/CharacterPanel';
import { getMissionObjective } from '../utils/missionObjective';
import { motion } from 'framer-motion';

interface DashboardProps {
  quests: Quest[];
  members: Member[];
  user: { username: string; role: string };
}

const Dashboard: React.FC<DashboardProps> = ({ quests, members, user }) => {
  const navigate = useNavigate();
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null);

  // Helper function to check if status matches (handles both old and new values)
  const matchesStatus = (quest: Quest, statuses: string[]): boolean => {
    return statuses.includes(quest.status);
  };

  // Helper function to get status display text
  const getStatusText = (status: string): string => {
    if (status === 'not_yet_begun' || status === 'pending') {
      return 'Not Yet Begun';
    }
    if (status === 'the_road_goes_ever_on' || status === 'in_progress') {
      return 'The Road Goes Ever On...';
    }
    if (status === 'it_is_done' || status === 'completed') {
      return 'It Is Done';
    }
    if (status === 'the_shadow_falls' || status === 'blocked') {
      return 'The Shadow Falls';
    }
    return String(status).replace(/_/g, ' ');
  };

  const stats = {
    total: quests.length,
    notYetBegun: quests.filter(q => matchesStatus(q, ['not_yet_begun', 'pending'])).length,
    inProgress: quests.filter(q => matchesStatus(q, ['the_road_goes_ever_on', 'in_progress'])).length,
    completed: quests.filter(q => matchesStatus(q, ['it_is_done', 'completed'])).length,
    shadowFalls: quests.filter(q => matchesStatus(q, ['the_shadow_falls', 'blocked'])).length,
    darkMagic: quests.filter(q => q.is_dark_magic).length,
  };

  const activeMembers = members.filter(m => m.status === 'active').length;
  const userQuests = quests.filter(q => q.assignee_name === user.role || q.assigned_to);
  const userCompleted = userQuests.filter(q => matchesStatus(q, ['it_is_done', 'completed'])).length;
  const completionRate = quests.length > 0 ? Math.round((stats.completed / quests.length) * 100) : 0;

  // Filter displayed quests based on selected status
  const displayedQuests = selectedStatus
    ? quests.filter(q => q.status === selectedStatus)
    : quests.slice(0, 8);

  const missionObjective = useMemo(() => getMissionObjective(quests), [quests]);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.5, ease: 'easeOut' },
    },
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-2 space-y-8">
      {/* Header Section */}
      <motion.div
        variants={itemVariants}
        initial="hidden"
        animate="visible"
        className="space-y-2"
      >
        <div className="flex items-center justify-between">
          <div>
            
            <p className="font-readable text-text-muted text-lg">
              Welcome, {user.role}! Track the Fellowship's journey through Middle-earth
            </p>
          </div>
        </div>
      </motion.div>

      {/* Dark Magic Warning */}
      {stats.darkMagic > 0 && (
        <motion.div variants={itemVariants} initial="hidden" animate="visible">
          <Alert
            variant="warning"
            title="Dark Magic Detected!"
          >
            {stats.darkMagic} quest{stats.darkMagic !== 1 ? 's have' : ' has'} been corrupted by Sauron's influence.
          </Alert>
        </motion.div>
      )}

      {/* Mission Briefing */}
      <motion.div variants={itemVariants} initial="hidden" animate="visible">
        <Card variant="dark" className="space-y-4" testId="mission-briefing">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="font-epic text-2xl text-gold">Mission Briefing</h2>
              <p className="font-readable text-parchment-light mt-2">{missionObjective.title}</p>
              <p className="text-sm text-parchment-light/80 mt-2">{missionObjective.description}</p>
            </div>
            <span className="text-3xl" aria-hidden="true">
              {missionObjective.mode === 'map' ? '🗺️' : '📜'}
            </span>
          </div>
          <div>
            <Button
              variant="epic"
              className="text-sm"
              data-testid="mission-briefing-cta"
              onClick={() => navigate(missionObjective.route)}
            >
              {missionObjective.ctaLabel}
            </Button>
          </div>
        </Card>
      </motion.div>

      {/* Stats Grid */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
      >
        {/* Total Quests */}
        <motion.div variants={itemVariants} className="h-full">
          <Card variant="parchment" className="cursor-pointer hover:shadow-lg transition-shadow h-full flex flex-col justify-center items-center min-h-[180px]">
        <div className="text-center py-4">
          <div className="text-4xl font-epic text-forest-dark mb-2">{stats.total}</div>
          <div className="text-sm font-readable text-text-muted">Total Quest Objectives</div>
          <div className="mt-3 flex justify-center">
            <Badge variant="standard">All Quests</Badge>
          </div>
        </div>
          </Card>
        </motion.div>

        {/* In Progress */}
        <motion.div variants={itemVariants} className="h-full">
          <Card
        variant="parchment"
        className="cursor-pointer hover:shadow-lg transition-shadow h-full flex flex-col justify-center items-center min-h-[180px]"
        onClick={() => setSelectedStatus('the_road_goes_ever_on')}
          >
        <div className="text-center py-4">
          <div className="text-4xl font-epic text-forest mb-2">{stats.inProgress}</div>
          <div className="text-sm font-readable text-text-muted">The Road Goes Ever On...</div>
          <div className="mt-3 flex justify-center">
            <Badge variant="inprogress">In Progress</Badge>
          </div>
        </div>
          </Card>
        </motion.div>

        {/* Completed */}
        <motion.div variants={itemVariants} className="h-full">
          <Card
        variant="parchment"
        className="cursor-pointer hover:shadow-lg transition-shadow h-full flex flex-col justify-center items-center min-h-[180px]"
        onClick={() => setSelectedStatus('it_is_done')}
          >
        <div className="text-center py-4">
          <div className="text-4xl font-epic text-success mb-2">{stats.completed}</div>
          <div className="text-sm font-readable text-text-muted">It Is Done</div>
          <div className="mt-3 flex justify-center">
            <Badge variant="ready">Completed</Badge>
          </div>
        </div>
          </Card>
        </motion.div>

        {/* Not Yet Begun */}
        <motion.div variants={itemVariants} className="h-full">
          <Card variant="parchment" className="cursor-pointer hover:shadow-lg transition-shadow h-full flex flex-col justify-center items-center min-h-[180px]">
        <div className="text-center py-4">
          <div className="text-4xl font-epic text-gray-600 mb-2">{stats.notYetBegun}</div>
          <div className="text-sm font-readable text-text-muted">Not Yet Begun</div>
          <div className="mt-3 flex justify-center">
            <Badge variant="pending">Planned</Badge>
          </div>
        </div>
          </Card>
        </motion.div>

        {/* Blocked */}
        <motion.div variants={itemVariants} className="h-full">
          <Card variant="parchment" className="cursor-pointer hover:shadow-lg transition-shadow h-full flex flex-col justify-center items-center min-h-[180px]">
        <div className="text-center py-4">
          <div className="text-4xl font-epic text-danger mb-2">{stats.shadowFalls}</div>
          <div className="text-sm font-readable text-text-muted">The Shadow Falls</div>
          <div className="mt-3 flex justify-center">
            <Badge variant="blocked">Blocked</Badge>
          </div>
        </div>
          </Card>
        </motion.div>

        {/* Fellowship Members */}
        <motion.div variants={itemVariants} className="h-full">
          <Card variant="parchment" className="cursor-pointer hover:shadow-lg transition-shadow h-full flex flex-col justify-center items-center min-h-[180px]">
        <div className="text-center py-4">
          <div className="text-4xl font-epic text-forest mb-2">{activeMembers}</div>
          <div className="text-sm font-readable text-text-muted">Active Fellowship Members</div>
        </div>
          </Card>
        </motion.div>
      </motion.div>

      {/* User Personal Stats */}
      {userQuests.length > 0 && (
        <motion.div variants={itemVariants} initial="hidden" animate="visible">
          <Card variant="dark">
            <div className="space-y-2">
              <h2 className="font-epic text-2xl text-gold mb-4">Your Personal Journey</h2>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-epic text-parchment mb-1">{userQuests.length}</div>
                  <div className="text-sm text-parchment-light">Assigned to You</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-epic text-success mb-1">{userCompleted}</div>
                  <div className="text-sm text-parchment-light">Completed</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-epic text-gold mb-1">{completionRate}%</div>
                  <div className="text-sm text-parchment-light">Completion Rate</div>
                </div>
              </div>
            </div>
          </Card>
        </motion.div>
      )}

      {/* Recent/Filtered Quests */}
      <motion.div variants={itemVariants} initial="hidden" animate="visible">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="font-epic text-2xl text-forest-dark">
              {selectedStatus ? 'Filtered Quests' : 'Recent Quest Objectives'}
            </h2>
            {selectedStatus && (
              <button
                onClick={() => setSelectedStatus(null)}
                className="px-4 py-2 text-sm rounded bg-forest text-parchment hover:bg-forest-dark transition-colors"
              >
                Clear Filter
              </button>
            )}
          </div>

          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="space-y-3 max-h-96 overflow-y-auto"
          >
            {displayedQuests.length > 0 ? (
              displayedQuests.map((quest, index) => (
                <motion.div key={quest.id} variants={itemVariants}>
                  <Card variant="parchment" className="hover:shadow-md transition-shadow">
                    <div className="space-y-2">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="font-epic text-lg text-forest-dark">{quest.title}</h3>
                          <p className="text-sm text-text-muted mt-1">{quest.description}</p>
                        </div>
                        <Badge variant={quest.is_dark_magic ? 'critical' : 'standard'}>
                          {getStatusText(quest.status)}
                        </Badge>
                      </div>
                      <div className="flex gap-4 text-xs text-text-muted">
                        {quest.location_name && (
                          <span>📍 {quest.location_name}</span>
                        )}
                        {quest.priority && (
                          <span>⚡ Priority: {quest.priority}</span>
                        )}
                      </div>
                    </div>
                  </Card>
                </motion.div>
              ))
            ) : (
              <div className="text-center py-8 text-text-muted">
                <p className="text-lg">No quests found with current criteria</p>
              </div>
            )}
          </motion.div>
        </div>
      </motion.div>

      {/* Clear Selection Footer */}
      {selectedStatus && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center text-sm text-text-muted"
        >
          Showing {displayedQuests.length} of {quests.length} quests
        </motion.div>
      )}
      </div>

      <div className="lg:col-span-1 lg:sticky lg:top-6 h-fit">
        <CharacterPanel />
      </div>
    </div>
  );
};

export default Dashboard;
