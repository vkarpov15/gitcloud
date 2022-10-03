import { useEffect, useState } from "react";
import {
  org as orgApi,
  repo as repoApi,
  roleAssignments as roleAssignmentsApi,
  roleChoices as roleChoicesApi,
} from "../../api";
import useUser from "../../lib/useUser";
import { useRouter } from "next/router";
import { MapPinIcon } from "@heroicons/react/20/solid";
import { RepositoryList } from "../../components/RepositoryList";
import LoadingPage from "../../components/LoadingPage";
import ErrorMessage from "../../components/ErrorMessage";
import Link from "next/link";
import Breadcrumbs from "../../components/Breadcrumbs";
import { gql, useQuery } from '@apollo/client';
import { useOrg } from "../../api/org";


const GET_REPOS = gql`
  query GetRepos($orgId: ID!) {
    org(id: $orgId) {
      id
      name
      billingAddress
      role
      permissions
      repos {
        id
        name
        issueCount
        permissions
        role
        public
        orgId
      }
    }
  }
`;

export default function Show() {
  const router = useRouter();
  const { orgId } = router.query as { orgId?: string };

  const {
    data: orgData,
    loading: orgLoading,
    error: orgError,
  } = useQuery(GET_REPOS, { variables: { orgId: orgId } })
  const [roleChoices, setRoleChoices] = useState<string[]>([]);
  useEffect(() => {
    roleChoicesApi.org().then(setRoleChoices);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (orgLoading) return <LoadingPage />;
  if (orgError) return <ErrorMessage error={orgError} />;

  if (!orgId || !orgData) return null;

  const org = orgData.org;
  const repos = orgData.org.repos;

  return (
    <>
      <div className="-ml-4  flex items-center justify-between flex-wrap sm:flex-nowrap">
        <div className="ml-4">
          <Breadcrumbs pages={[]} />
          <div className="lg:flex lg:items-center lg:justify-between">
            <div className="flex-1 min-w-0">
              <h2 className="mt-2 text-2xl font-bold leading-7 text-gray-900 sm:text-3xl sm:tracking-tight sm:truncate">
                {org.name}
              </h2>
              <div className="mt-1 flex flex-col sm:flex-row sm:flex-wrap sm:mt-0 sm:space-x-6">
                <div className="mt-2 flex items-center text-sm text-gray-500">
                  <MapPinIcon
                    className="flex-shrink-0 mr-1.5 h-5 w-5 text-gray-400"
                    aria-hidden="true"
                  />
                  {org.billingAddress}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="ml-4 mt-4 flex-shrink-0">
          {
            org.permissions?.includes("view_members") &&
            <Link href={{ pathname: "/orgs/[orgId]/settings", query: { orgId } }}>
              <button
                type="button"
                className="relative inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
              >
                Settings
              </button>
            </Link>
          }
        </div>
      </div>
      <div className="mt-8 bg-white px-4 py-5 border-b border-gray-200 sm:px-6">
        <div className="-ml-4 -mt-2 flex items-center justify-between flex-wrap sm:flex-nowrap">
          <div className="ml-4 mt-2">
            <h3 className="text-lg leading-6 font-medium text-gray-900">
              Repositories
            </h3>
          </div>
          <div className="ml-4 mt-2 flex-shrink-0">
            {
              org.permissions?.includes("create_repositories") &&
              <Link href={{ pathname: "/orgs/[orgId]/repos/new", query: { orgId } }}>
                <button
                  type="button"
                  className="relative inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
                >
                  Create new repository
                </button>
              </Link>
            }
          </div>
        </div>
      </div>

      <RepositoryList repositories={repos || []} />
    </>
  );
}
