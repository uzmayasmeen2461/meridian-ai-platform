import type { Role } from './types';

export interface IdentityOption {
  user_id: string;
  name: string;
  email: string;
  role: Role;
  group_id: string;
}

export const identities: IdentityOption[] = [
  { user_id: 'user_E7691888F28227066DD2FB86', name: 'Priya Nair', email: 'priya.nair@meridianls.example', role: 'team_lead', group_id: 'clinical-operations' },
  { user_id: 'user_699C48763F6FA2958D2CDB5D', name: 'Daniel Okafor', email: 'daniel.okafor@meridianls.example', role: 'member', group_id: 'clinical-operations' },
  { user_id: 'user_B1AA49EEED515A8B4C2254F5', name: 'Aisha Rahman', email: 'aisha.rahman@meridianls.example', role: 'member', group_id: 'clinical-operations' },
  { user_id: 'user_5259D5870F22E6611FE78F49', name: 'Tomasz Kowalski', email: 'tomasz.kowalski@meridianls.example', role: 'member', group_id: 'clinical-operations' },
  { user_id: 'user_B3DEF4602E6A0912588C6D50', name: 'Mei Chen', email: 'mei.chen@meridianls.example', role: 'team_lead', group_id: 'regulatory-affairs' },
  { user_id: 'user_7E98033B84A18835BAAC3FD2', name: 'Lucas Moreau', email: 'lucas.moreau@meridianls.example', role: 'member', group_id: 'regulatory-affairs' },
  { user_id: 'user_E3F6880CD4C96210FF515D1B', name: 'Fatima Haddad', email: 'fatima.haddad@meridianls.example', role: 'member', group_id: 'regulatory-affairs' },
  { user_id: 'user_665DCB103C2F8DEE3C946C7A', name: 'Jonas Lindqvist', email: 'jonas.lindqvist@meridianls.example', role: 'member', group_id: 'regulatory-affairs' },
  { user_id: 'user_0CF0516C4D9067BED584DB3F', name: 'Sofia Rossi', email: 'sofia.rossi@meridianls.example', role: 'team_lead', group_id: 'finance' },
  { user_id: 'user_BF28D9E864C2318ED312A3F5', name: 'Ravi Iyer', email: 'ravi.iyer@meridianls.example', role: 'member', group_id: 'finance' },
  { user_id: 'user_454C30EA4FD6317D4D3390BD', name: 'Hannah Fischer', email: 'hannah.fischer@meridianls.example', role: 'member', group_id: 'finance' },
  { user_id: 'user_EFD3FFD905F1F3A62F1AE916', name: 'Diego Alvarez', email: 'diego.alvarez@meridianls.example', role: 'team_lead', group_id: 'hr' },
  { user_id: 'user_4DDA8BD860906E1802392E9E', name: 'Yuki Tanaka', email: 'yuki.tanaka@meridianls.example', role: 'member', group_id: 'hr' },
  { user_id: 'user_337387845926467C11D43128', name: 'Marcus Bennett', email: 'marcus.bennett@meridianls.example', role: 'member', group_id: 'hr' },
  { user_id: 'user_FA89F4D169328073239C6B6E', name: 'Elena Petrova', email: 'elena.petrova@meridianls.example', role: 'team_lead', group_id: 'medical-writing' },
  { user_id: 'user_27A35769D5401F23F6A15604', name: 'Samuel Adeyemi', email: 'samuel.adeyemi@meridianls.example', role: 'member', group_id: 'medical-writing' },
  { user_id: 'user_CA8D914FC4B2D868B1016428', name: 'Ingrid Solberg', email: 'ingrid.solberg@meridianls.example', role: 'member', group_id: 'medical-writing' },
  { user_id: 'user_D513BD91AAB20411FC510A2A', name: 'Kwame Mensah', email: 'kwame.mensah@meridianls.example', role: 'team_lead', group_id: 'it-platform' },
  { user_id: 'user_533B58E6F66C98ACB833527A', name: 'Chloe Dubois', email: 'chloe.dubois@meridianls.example', role: 'platform_admin', group_id: 'it-platform' },
  { user_id: 'user_20FFD6524F256B8D69E6E2F2', name: 'Arjun Mehta', email: 'arjun.mehta@meridianls.example', role: 'platform_admin', group_id: 'it-platform' },
  { user_id: 'user_39F097897A80367CEA4152ED', name: 'Nadia Karim', email: 'nadia.karim@meridianls.example', role: 'member', group_id: 'it-platform' },
  { user_id: 'user_AC569166A0A94D7A4B14DBEB', name: 'Felix Bauer', email: 'felix.bauer@meridianls.example', role: 'member', group_id: 'it-platform' }
];
