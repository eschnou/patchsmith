/**
 * @name Test query - Find all functions
 * @description Simple test query to verify CodeQL query execution
 * @kind problem
 * @problem.severity warning
 * @id py/test-query
 * @tags test
 */

import python

from Function f
where exists(f)
select f, "Found a function: " + f.getName()
