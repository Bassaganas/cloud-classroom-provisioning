import { Alert, Snackbar } from '@mui/material'

function AppToast({ toast, onClose, autoHideDuration = 4000 }) {
  return (
    <Snackbar
      open={toast.open}
      autoHideDuration={autoHideDuration}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
    >
      <Alert onClose={onClose} severity={toast.severity || 'info'} variant="filled" sx={{ width: '100%' }}>
        {toast.message}
      </Alert>
    </Snackbar>
  )
}

export default AppToast
