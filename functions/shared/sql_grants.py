"""
sql_grants.py — T-SQL GRANT/REVOKE/DENY script generator and executor.

Generates and executes T-SQL statements for compute-level security on
Fabric SQL analytics endpoints. Handles:
  - Schema-level GRANT/DENY
  - Role membership (db_datareader, db_datawriter, custom roles)
  - Row-Level Security (RLS) role assignment
  - Variable substitution for Entra group SIDs and SPN app IDs

Usage:
    generator = SqlGrantGenerator(access_package)
    scripts = generator.generate_scripts()
    executor = SqlGrantExecutor(connection_string)
    results = executor.execute_all(scripts)
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import pyodbc

logger = logging.getLogger(__name__)


@dataclass
class SqlScript:
    """A single T-SQL script to execute."""
    statement: str
    description: str
    category: str  # "grant" | "deny" | "revoke" | "role_membership" | "rls"
    idempotent: bool = True  # Safe to re-run


@dataclass
class SqlExecutionResult:
    """Result of executing a SQL script."""
    script: SqlScript
    success: bool
    error: Optional[str] = None
    rows_affected: int = 0


# ---------------------------------------------------------------------------
# Script Generator
# ---------------------------------------------------------------------------
class SqlGrantGenerator:
    """
    Generates T-SQL security scripts from an access package definition.

    Reads the `compute.sql_endpoint` section of a YAML access package and
    produces idempotent T-SQL statements that can be executed against the
    Fabric SQL analytics endpoint.

    Variable substitution:
      ${ENTRA_GROUP_SID}  → Replaced with the Entra group's SID
      ${SPN_APP_ID}       → Replaced with the service principal's app ID
      ${PRINCIPAL_NAME}   → Replaced with the principal display name
    """

    def __init__(self, access_package: dict, variables: dict[str, str]):
        """
        Args:
            access_package: Parsed YAML access package dictionary
            variables: Substitution variables (e.g., ENTRA_GROUP_SID, SPN_APP_ID)
        """
        self.package = access_package
        self.variables = variables
        self.compute_config = access_package.get("grants", {}).get("compute", {})
        self.sql_config = self.compute_config.get("sql_endpoint", {})

    def generate_scripts(self) -> list[SqlScript]:
        """Generate all T-SQL scripts for the access package."""
        scripts = []

        # Ensure the external principal exists in the database
        scripts.append(self._create_user_script())

        # Process explicit GRANT statements
        for grant in self.sql_config.get("grants", []):
            scripts.append(SqlScript(
                statement=self._substitute(grant),
                description=f"Grant: {grant}",
                category="grant",
            ))

        # Process explicit DENY statements
        for deny in self.sql_config.get("deny", []):
            scripts.append(SqlScript(
                statement=self._substitute(deny),
                description=f"Deny: {deny}",
                category="deny",
            ))

        # Process RLS role assignment
        rls_role = self.sql_config.get("rls_role")
        if rls_role:
            scripts.extend(self._rls_scripts(rls_role))

        return scripts

    def generate_revocation_scripts(self) -> list[SqlScript]:
        """Generate T-SQL scripts to revoke all permissions for this package."""
        scripts = []

        # Revoke all explicit grants
        for grant in self.sql_config.get("grants", []):
            revoke_stmt = grant.replace("GRANT", "REVOKE")
            # Remove the FROM/TO distinction for REVOKE
            revoke_stmt = re.sub(r'\bTO\b', 'FROM', revoke_stmt)
            scripts.append(SqlScript(
                statement=self._substitute(revoke_stmt),
                description=f"Revoke: {grant}",
                category="revoke",
            ))

        # Remove DENY statements (restore default)
        for deny in self.sql_config.get("deny", []):
            revoke_stmt = deny.replace("DENY", "REVOKE")
            revoke_stmt = re.sub(r'\bTO\b', 'FROM', revoke_stmt)
            scripts.append(SqlScript(
                statement=self._substitute(revoke_stmt),
                description=f"Revoke deny: {deny}",
                category="revoke",
            ))

        # Remove RLS role
        rls_role = self.sql_config.get("rls_role")
        if rls_role:
            principal = self._get_principal_name()
            scripts.append(SqlScript(
                statement=f"ALTER ROLE [{rls_role}] DROP MEMBER [{principal}]",
                description=f"Remove from RLS role: {rls_role}",
                category="role_membership",
            ))

        return scripts

    def _create_user_script(self) -> SqlScript:
        """Generate idempotent CREATE USER for external principal."""
        principal = self._get_principal_name()
        return SqlScript(
            statement=f"""
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = '{principal}')
BEGIN
    CREATE USER [{principal}] FROM EXTERNAL PROVIDER;
END
""".strip(),
            description=f"Ensure external user exists: {principal}",
            category="grant",
            idempotent=True,
        )

    def _rls_scripts(self, rls_role: str) -> list[SqlScript]:
        """Generate RLS role membership scripts."""
        principal = self._get_principal_name()
        return [
            SqlScript(
                statement=f"""
IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members rm
    JOIN sys.database_principals r ON rm.role_principal_id = r.principal_id
    JOIN sys.database_principals m ON rm.member_principal_id = m.principal_id
    WHERE r.name = '{rls_role}' AND m.name = '{principal}'
)
BEGIN
    ALTER ROLE [{rls_role}] ADD MEMBER [{principal}];
END
""".strip(),
                description=f"Add {principal} to RLS role {rls_role}",
                category="rls",
                idempotent=True,
            )
        ]

    def _substitute(self, template: str) -> str:
        """Replace ${VAR} placeholders with actual values."""
        result = template
        for key, value in self.variables.items():
            result = result.replace(f"${{{key}}}", value)
        return result

    def _get_principal_name(self) -> str:
        """Get the principal name for SQL statements."""
        return self.variables.get("PRINCIPAL_NAME",
                                  self.variables.get("ENTRA_GROUP_SID",
                                                     self.variables.get("SPN_APP_ID", "unknown")))


# ---------------------------------------------------------------------------
# Script Executor
# ---------------------------------------------------------------------------
class SqlGrantExecutor:
    """
    Executes T-SQL scripts against a Fabric SQL analytics endpoint.

    Connection uses Entra ID authentication (ActiveDirectoryServicePrincipal).
    The executing SPN must have sufficient permissions on the SQL endpoint
    to execute GRANT/DENY/ALTER ROLE statements.
    """

    def __init__(self, server: str, database: str,
                 tenant_id: str, client_id: str, client_secret: str):
        """
        Args:
            server: SQL endpoint hostname (e.g., "xxxx.datawarehouse.fabric.microsoft.com")
            database: Database name (typically the lakehouse/warehouse name)
        """
        self.connection_string = (
            f"DRIVER={{ODBC Driver 18 for SQL Server}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"Authentication=ActiveDirectoryServicePrincipal;"
            f"UID={client_id}@{tenant_id};"
            f"PWD={client_secret};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
        )

    def execute_all(self, scripts: list[SqlScript]) -> list[SqlExecutionResult]:
        """Execute a list of SQL scripts, returning results for each."""
        results = []
        try:
            conn = pyodbc.connect(self.connection_string, timeout=30)
            cursor = conn.cursor()

            for script in scripts:
                result = self._execute_single(cursor, script)
                results.append(result)

                if not result.success:
                    logger.error(f"Script failed: {script.description} — {result.error}")

            conn.commit()
            conn.close()

        except pyodbc.Error as e:
            logger.error(f"Database connection failed: {e}")
            # Mark all remaining scripts as failed
            for script in scripts[len(results):]:
                results.append(SqlExecutionResult(
                    script=script, success=False,
                    error=f"Connection failed: {str(e)}"
                ))

        return results

    def _execute_single(self, cursor, script: SqlScript) -> SqlExecutionResult:
        """Execute a single SQL script."""
        try:
            logger.info(f"Executing: {script.description}")
            cursor.execute(script.statement)
            rows = cursor.rowcount
            return SqlExecutionResult(
                script=script, success=True, rows_affected=max(rows, 0)
            )
        except pyodbc.Error as e:
            return SqlExecutionResult(
                script=script, success=False, error=str(e)
            )


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------
def provision_sql_access(access_package: dict, variables: dict,
                         server: str, database: str,
                         tenant_id: str, client_id: str,
                         client_secret: str) -> list[SqlExecutionResult]:
    """
    End-to-end: generate and execute SQL grants for an access package.

    Returns list of execution results for audit logging.
    """
    generator = SqlGrantGenerator(access_package, variables)
    scripts = generator.generate_scripts()

    executor = SqlGrantExecutor(server, database, tenant_id, client_id, client_secret)
    return executor.execute_all(scripts)


def revoke_sql_access(access_package: dict, variables: dict,
                      server: str, database: str,
                      tenant_id: str, client_id: str,
                      client_secret: str) -> list[SqlExecutionResult]:
    """
    End-to-end: generate and execute SQL revocations for an access package.
    """
    generator = SqlGrantGenerator(access_package, variables)
    scripts = generator.generate_revocation_scripts()

    executor = SqlGrantExecutor(server, database, tenant_id, client_id, client_secret)
    return executor.execute_all(scripts)
