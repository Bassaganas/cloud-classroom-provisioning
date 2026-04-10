export const EC2_INSTANCE_TYPE_OPTIONS = [
  { value: 't3.small', vcpu: 2, ramGiB: 2, hourlyUsd: 0.0208 },
  { value: 't3.medium', vcpu: 2, ramGiB: 4, hourlyUsd: 0.0416 },
  { value: 't3.large', vcpu: 2, ramGiB: 8, hourlyUsd: 0.0832 },
  { value: 't2.small', vcpu: 1, ramGiB: 2, hourlyUsd: 0.0232 },
  { value: 't2.medium', vcpu: 2, ramGiB: 4, hourlyUsd: 0.0464 },
  { value: 't2.large', vcpu: 2, ramGiB: 8, hourlyUsd: 0.0928 },
]

export const DEFAULT_EC2_INSTANCE_TYPE = 't3.medium'

export function formatEc2OptionLabel(option) {
  return `${option.value} (${option.vcpu} vCPU, ${option.ramGiB} GiB RAM, $${option.hourlyUsd.toFixed(4)}/hr)`
}

export const EC2_ON_DEMAND_RATES = EC2_INSTANCE_TYPE_OPTIONS.reduce((acc, option) => {
  acc[option.value] = { onDemand: option.hourlyUsd, spot: Math.max(option.hourlyUsd * 0.3, 0.0001) }
  return acc
}, {})
