import context from '../../configs/app.config'

export default defineAppConfig({
  ...context,

  /** Public routes that do not require authentication */
  publicRoutes: new Set(['/login']),
  /** Path to redirect before authentication */
  loginRoute: '/login',
  /** Path to redirect after successful login */
  loggedinRedirectRoute: '/repositories',
})
