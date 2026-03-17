import { useMemo, useState } from 'react'
import {
  Alert,
  Box,
  Chip,
  Stack,
  TextField,
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

function PurchaseTypeSelector({ onPurchaseTypeChange, instanceType = 'pool', session = null }) {
  const [purchaseType, setPurchaseType] = useState('on-demand')
  const [spotMaxPrice, setSpotMaxPrice] = useState('')

  const handlePurchaseTypeChange = (value, nextSpotMaxPrice = spotMaxPrice) => {
    setPurchaseType(value)
    if (value !== 'spot') {
      setSpotMaxPrice('')
    }
    onPurchaseTypeChange({
      purchase_type: value,
      spot_duration_hours: null,
      spot_max_price: value === 'spot' ? (nextSpotMaxPrice || null) : null
    })
  }

  const defaultSpotPrice = session?.spot_max_price ? `$${session.spot_max_price}` : 'market price'
  const hasHighSpotPrice = Number(spotMaxPrice) > 1

  const estimatedCost = useMemo(() => {
    const onDemandPrice = PRICING[INSTANCE_TYPE]['on-demand']
    const spotPrice = PRICING[INSTANCE_TYPE].spot

    if (purchaseType === 'spot') {
      const onDemandCost = onDemandPrice * 1
      const spotCost = spotPrice * 1
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
  }, [purchaseType])

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
        Spot instances reduce cost and can be stopped by classroom lifecycle controls.
      </Alert>

      {purchaseType === 'spot' && (
        <Stack spacing={0.75}>
          <TextField
            type="number"
            label="Spot Max Price ($/hour, optional)"
            inputProps={{ min: 0.0001, step: 0.0001 }}
            value={spotMaxPrice}
            onChange={(event) => {
              const nextValue = event.target.value
              setSpotMaxPrice(nextValue)
              handlePurchaseTypeChange('spot', nextValue)
            }}
            error={hasHighSpotPrice}
            helperText={`Default: ${defaultSpotPrice}/h. Leave empty to use tutorial default (typically 2-3x the on-demand price for better availability).`}
            FormHelperTextProps={hasHighSpotPrice ? { sx: { color: 'error.main' } } : undefined}
          />
          {hasHighSpotPrice && (
            <Alert severity="error" sx={{ py: 0.25 }}>
              Spot max price is unusually high (&gt; $1.00/h). Please confirm before continuing.
            </Alert>
          )}
        </Stack>
      )}

      {purchaseType === 'spot' && instanceType === 'admin' && (
        <Alert severity="warning" sx={{ py: 0.25 }}>
          Admin lifecycle still follows cleanup policy and timeout settings.
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
