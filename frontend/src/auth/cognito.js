/**
 * Wrapper on amazon-cognito-identity-js
 * 
 * Sign in, sign up, etc.
 */

import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
} from 'amazon-cognito-identity-js';
import { config } from '../config.js';

let pool = null;

/** Get the user pool */
function userPool() {
  if (!pool) {
    pool = new CognitoUserPool({
      UserPoolId: config.userPoolId,
      ClientId: config.userPoolClientId,
    });
  }
  return pool;
}

function cognitoUser(email) {
  return new CognitoUser({ Username: email, Pool: userPool() });
}

/** Sign up new user. Confirmation email is sent. */
export function signUp(email, password) {
  return new Promise((resolve, reject) => {
    const attributes = [
      new CognitoUserAttribute({ Name: 'email', Value: email }),
    ];
    userPool().signUp(email, password, attributes, null, (err, result) => {
      if (err) return reject(err);
      resolve(result);
    });
  });
}

/** Confirm sign up with the verification code */
export function confirmSignUp(email, code) {
  return new Promise((resolve, reject) => {
    cognitoUser(email).confirmRegistration(code, true, (err, result) => {
      if (err) return reject(err);
      resolve(result);
    });
  });
}

/** Resend confirmation code */
export function resendConfirmationCode(email) {
  return new Promise((resolve, reject) => {
    cognitoUser(email).resendConfirmationCode((err, result) => {
      if (err) return reject(err);
      resolve(result);
    });
  });
}

/** Sign in with SRP */
export function signIn(email, password) {
  return new Promise((resolve, reject) => {
    const user = cognitoUser(email);
    const details = new AuthenticationDetails({
      Username: email,
      Password: password,
    });
    user.authenticateUser(details, {
      onSuccess: (session) => {
        resolve(sessionToUser(user, session));
      },
      onFailure: (err) => reject(err),
      newPasswordRequired: () =>
        reject(new Error('A password reset is required. Please contact support.')),
    });
  });
}

/** Return the signed-in user or null if logged out */
export function getCurrentUser() {
  return new Promise((resolve) => {
    const user = userPool().getCurrentUser();
    if (!user) return resolve(null);
    user.getSession((err, session) => {
      if (err || !session || !session.isValid()) return resolve(null);
      resolve(sessionToUser(user, session));
    });
  });
}

export function signOut() {
  const user = userPool().getCurrentUser();
  if (user) user.signOut();
}

function sessionToUser(user, session) {
  const idToken = session.getIdToken();
  const payload = idToken.decodePayload();
  return {
    email: payload.email || user.getUsername(),
    sub: payload.sub,
    idToken: idToken.getJwtToken(),
  };
}
