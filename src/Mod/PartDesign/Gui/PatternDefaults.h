// SPDX-License-Identifier: LGPL-2.1-or-later

#pragma once

#include <optional>
#include <vector>

#include <Base/Vector3D.h>

class TopoDS_Shape;

namespace App
{
class DocumentObject;
class PropertyLinkSub;
}  // namespace App
namespace PartDesign
{
class LinearPattern;
}

namespace PartDesignGui
{

/// Rounds a spacing up to a whole mm, or to 0.1 mm below 10 mm.
double roundUpSpacing(double value);

/// The spacing that puts copies just clear of each other: the originals' size along
/// direction (body coordinates) times 1.5, rounded up. With allowGaps false the copies
/// touch instead (factor 1.0), for bodies that must stay one solid. 10 mm when the
/// originals have no size along direction.
double suggestPatternSpacing(
    const std::vector<App::DocumentObject*>& originals,
    const Base::Vector3d& direction,
    bool allowGaps = true
);

/// The same spacing, measured from a single already-placed shape rather than a list of
/// originals. Used in whole-body mode, where there are no originals to measure: the
/// caller sizes from the base feature's own shape instead, the way getStartPoint() falls
/// back to it.
double suggestPatternSpacing(
    const TopoDS_Shape& shape,
    const Base::Vector3d& direction,
    bool allowGaps = true
);

/// Direction of a linear pattern's direction link in body coordinates, or nullopt when
/// the link is empty or does not resolve to a direction.
std::optional<Base::Vector3d> patternDirection(
    const PartDesign::LinearPattern& pattern,
    const App::PropertyLinkSub& link
);

}  // namespace PartDesignGui
