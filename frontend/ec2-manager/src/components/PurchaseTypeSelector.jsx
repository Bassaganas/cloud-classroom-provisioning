import { useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Button,
  Chip,
  Slider,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography
} from '@mui/material'

const PRICING = {
  't3.small': {
    'on-demand': 0.022,
    spot: 0.0066
  }
}

const INSTANCE_TYPE = 't3.small'
const MIN_DURATION = 1
const MAX_DURATION = 6

function PurchaseTypeSelector({ onPurchaseTypeChange, instanceType = 'pool' }) {
  const [purchaseType, setPurchaseType] = useState('on-demand')
  const [spotDurationHours, setSpotDurationHours] = useState(2)

  const handlePurchaseTypeChange = (value) => {
    setPurchaseType(value)
    onPurchaseTypeChange({
      purchase_type: value,
      spot_duration_hours: value === 'spot' ? spotDurationHours : null
    })
  }

  const handleSpotDurationChange = (value) => {
    setSpotDurationHours(value)
    onPurchaseTypeChange({
      purchase_type: 'spot',
      spot_duration_hours: value
    })
  }

  const estimatedCost = useMemo(() => {
    const onDemandPrice = PRICING[INSTANCE_TYPE]['on-demand']
    const spotPrice = PRICING[INSTANCE_TYPE].spot

    if (purchaseType === 'spot') {
      const onDemandCost = onDemandPrice * spotDurationHours
      const spotCost = spotPrice * spotDurationHours
      const savings = onDemandCost - spotCost
      const savingsPercent = onDemandCost > 0 ? Math.round((savings / onDemandCost) * 100) : 0

      return {
        onDemandCost: onDemandCost.toFixed(2),
        spotCost: spotCost.toFixed(2),
        savings: savings.toFixed(2),
        savingsPercent
      }
    }

    return {
      onDemandCost: (onDemandPrice * 1).toFixed(2),
      spotCost: null,
      savings: null,
      savingsPercent: null
    }
  }, [purchaseType, spotDurationHours])

  const quickDurations = [1, 2, 3, 4, 5, 6]

  return (
    <Stack spacing={1.5}>
      <Typography variant="subtitle1" fontWeight={700}>Instance Purchase Type</Typography>

      <ToggleButtonGroup
        color="primary"
        exclusive
        value={purchaseType}
        onChange={(_, value) => {
          if (value) handlePurchaseTypeChange(value)
        }}
        fullWidth
      >
        <ToggleButton value="on-demand">On-Demand</ToggleButton>
        <ToggleButton value="spot">Spot (-70%)</ToggleButton>
      </ToggleButtonGroup>

      {purchaseType === 'spot' && (
        <Box sx={{ px: 0.5 }}>
          <Typography variant="body2" sx={{ mb: 0.5 }}>
            Reservation Duration: <strong>{spotDurationHours}h</strong>
          </Typography>
          <Slider
            value={spotDurationHours}
            onChange={(_, value) => handleSpotDurationChange(value)}
            min={MIN_DURATION}
            max={MAX_DURATION}
            step={0.25}
            marks={[{ value: MIN_DURATION, label: '1h' }, { value: MAX_DURATION, label: '6h' }]}
            valueLabelDisplay="auto"
          />
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            {quickDurations.map((duration) => (
              <Button
                key={duration}
                size="small"
                variant={spotDurationHours === duration ? 'contained' : 'outlined'}
                onClick={() => handleSpotDurationChange(duration)}
              >
                {duration}h
              </Button>
            ))}
          </Stack>
        </Box>
      )}

      <Box sx={{ border: '1px solid', borderColor: 'divider', borderRadius: 2, p: 1.25, bgcolor: 'background.paper' }}>
        {purchaseType === 'spot' ? (
          <Stack spacing={0.75}>
            <SummaryRow label="On-demand cost" value={`$${estimatedCost.onDemandCost}`} muted />
            <SummaryRow label="Spot cost" value={`$${estimatedCost.spotCost}`} />
            <SummaryRow label="Savings" value={`$${estimatedCost.savings} (${estimatedCost.savingsPercent}%)`} highlight />
          </Stack>
        ) : (
          <SummaryRow label="Estimated cost (1 hour)" value={`$${estimatedCost.onDemandCost}`} />
        )}
      </Box>

      <Alert severity="info" sx={{ py: 0.25 }}>
        Spot capacity blocks are ideal for time-bounded tutorials and are guaranteed for the selected duration.
      </Alert>

      {purchaseType === 'spot' && instanceType === 'admin' && (
        <Alert severity="warning" sx={{ py: 0.25 }}>
          Admin instance will terminate automatically after {spotDurationHours} hour{spotDurationHours !== 1 ? 's' : ''}.
        </Alert>
      )}
    </Stack>
  )
}

function SummaryRow({ label, value, muted = false, highlight = false }) {
  return (
    <Stack direction="row" justifyContent="space-between" alignItems="center">
      <Typography variant="body2" color="text.secondary">{label}</Typography>
      <Chip
        size="small"
        label={value}
        color={highlight ? 'success' : 'default'}
        variant={muted ? 'outlined' : 'filled'}
      />
    </Stack>
  )
}

export default PurchaseTypeSelector
